from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from arroyo.backends.kafka import KafkaPayload
from arroyo.types import BrokerValue, Message, Partition, Topic
from freezegun import freeze_time

from sentry.constants import DataCategory
from sentry.ingest.billing_metrics_consumer import (
    BillingTxCountMetricConsumerStrategy,
    MetricsBucket,
)
from sentry.sentry_metrics.indexer.strings import TRANSACTION_METRICS_NAMES
from sentry.utils import json
from sentry.utils.outcomes import Outcome


@mock.patch("sentry.ingest.billing_metrics_consumer.track_outcome")
@freeze_time("1985-10-26 21:00:00")
def test_outcomes_consumed(track_outcome):
    # Based on test_ingest_consumer_kafka.py

    topic = Topic("snuba-generic-metrics")

    empty_tags: dict[str, str] = {}
    buckets: list[MetricsBucket] = [
        {  # Counter metric with wrong ID will not generate an outcome
            "metric_id": 123,
            "type": "c",
            "org_id": 1,
            "project_id": 2,
            "timestamp": 123,
            "value": 123.4,
            "tags": empty_tags,
        },
        {  # Distribution metric with wrong ID will not generate an outcome
            "metric_id": 123,
            "type": "d",
            "org_id": 1,
            "project_id": 2,
            "timestamp": 123456,
            "value": [1.0, 2.0],
            "tags": empty_tags,
        },
        {  # Empty distribution will not generate an outcome
            # NOTE: Should not be emitted by Relay anyway
            "metric_id": TRANSACTION_METRICS_NAMES["d:transactions/duration@millisecond"],
            "type": "d",
            "org_id": 1,
            "project_id": 2,
            "timestamp": 123456,
            "value": [],
            "tags": empty_tags,
        },
        {  # Valid distribution bucket emits an outcome
            "metric_id": TRANSACTION_METRICS_NAMES["d:transactions/duration@millisecond"],
            "type": "d",
            "org_id": 1,
            "project_id": 2,
            "timestamp": 123456,
            "value": [1.0, 2.0, 3.0],
            "tags": empty_tags,
        },
        {  # Another bucket to introduce some noise
            "metric_id": 123,
            "type": "c",
            "org_id": 1,
            "project_id": 2,
            "timestamp": 123456,
            "value": 123.4,
            "tags": empty_tags,
        },
        {  # Bucket with profiles
            "metric_id": TRANSACTION_METRICS_NAMES["d:transactions/duration@millisecond"],
            "type": "d",
            "org_id": 1,
            "project_id": 2,
            "timestamp": 123456,
            "value": [4.0],
            "tags": {f"{(1 << 63) + 260}": "true"},
        },
    ]

    fake_commit = mock.MagicMock()

    strategy = BillingTxCountMetricConsumerStrategy(
        commit=fake_commit,
    )

    generate_kafka_message_counter = 0

    def generate_kafka_message(bucket: MetricsBucket) -> Message[KafkaPayload]:
        nonlocal generate_kafka_message_counter

        encoded = json.dumps(bucket).encode()
        payload = KafkaPayload(key=None, value=encoded, headers=[])
        message = Message(
            BrokerValue(
                payload,
                Partition(topic, index=0),
                generate_kafka_message_counter,
                datetime.now(timezone.utc),
            )
        )
        generate_kafka_message_counter += 1
        return message

    # Mimick the behavior of StreamProcessor._run_once: Call poll repeatedly,
    # then call submit when there is a message.
    strategy.poll()
    strategy.poll()
    assert track_outcome.call_count == 0
    for i, bucket in enumerate(buckets):
        strategy.poll()
        assert fake_commit.call_count == i
        strategy.submit(generate_kafka_message(bucket))
        # commit is called for every message, and later debounced by arroyo's policy
        assert fake_commit.call_count == (i + 1)
        if i < 3:
            assert track_outcome.call_count == 0
        elif i < 5:
            assert track_outcome.mock_calls == [
                mock.call(
                    org_id=1,
                    project_id=2,
                    key_id=None,
                    outcome=Outcome.ACCEPTED,
                    reason=None,
                    timestamp=datetime(1985, 10, 26, 21, 00, 00, tzinfo=timezone.utc),
                    event_id=None,
                    category=DataCategory.TRANSACTION,
                    quantity=3,
                ),
            ]
        else:
            assert track_outcome.mock_calls[1:] == [
                mock.call(
                    org_id=1,
                    project_id=2,
                    key_id=None,
                    outcome=Outcome.ACCEPTED,
                    reason=None,
                    timestamp=datetime(1985, 10, 26, 21, 00, 00, tzinfo=timezone.utc),
                    event_id=None,
                    category=DataCategory.TRANSACTION,
                    quantity=1,
                ),
                mock.call(
                    org_id=1,
                    project_id=2,
                    key_id=None,
                    outcome=Outcome.ACCEPTED,
                    reason=None,
                    timestamp=datetime(1985, 10, 26, 21, 00, 00, tzinfo=timezone.utc),
                    event_id=None,
                    category=DataCategory.PROFILE,
                    quantity=1,
                ),
            ]

    assert fake_commit.call_count == 6

    # Joining should commit the offset of the last message:
    strategy.join()

    assert fake_commit.call_count == 7
