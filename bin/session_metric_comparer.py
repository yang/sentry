#!/usr/bin/env python
from collections import defaultdict
from math import isclose

from sentry.runner import configure

configure()

import argparse

from sentry.utils import json


def main():
    with open("session_metric_map.json") as map_file:
        session_metric_map = json.loads(map_file.read())

    with open("session-logs.json") as session_file:
        session_logs = json.loads(session_file.read())

    with open("metric-logs.json") as metric_file:
        metric_logs = json.loads(metric_file.read())

    metric_subscription_lookup = defaultdict(dict)
    for metric_log in metric_logs:
        payload = metric_log["jsonPayload"]
        metric_subscription_lookup[int(payload["subscription_id"])][
            payload["result"]["timestamp"]
        ] = payload

    for session_log in session_logs:
        session_payload = session_log["jsonPayload"]
        timestamp = session_payload["result"]["timestamp"]
        session_sub_id = str(session_payload["subscription_id"])
        if session_sub_id not in session_metric_map:
            # print(f"No corresponding metric subscription for session subscription {session_sub_id}")
            # This is fine, there aren't necessarily corresponding metric subscriptions for all
            # existing session subscriptions, since new session subscriptions may have been made
            # after we ran the creation script
            continue

        related_metric_sub_id = session_metric_map[session_sub_id]
        metric_subscription_results = metric_subscription_lookup[related_metric_sub_id]
        if timestamp in metric_subscription_results:
            metric_payload = metric_subscription_results[timestamp]
            session_value = session_payload.get("aggregation_value")
            metric_value = metric_payload.get("aggregation_value")

            if session_value is None and metric_value is None:
                continue

            if session_value is None or metric_value is None:
                # print(f"Received `None` for one metric, and a value for another. Session: {session_value}, Metric: {metric_value}")
                continue

            if not isclose(session_value, metric_value, abs_tol=1):
                print("timestamp", timestamp)
                print(
                    f"Aggregation value did not match for sessions vs metrics. "
                    f"Session value: {session_value}, "
                    f"Metric value: {metric_value},  "
                    f"session_sub_id: {session_sub_id}, "
                    f"metric_sub_id: {related_metric_sub_id}"
                    f"\nsession query: {session_payload['result']['request']['query']}"
                    f"\nmetric query: {metric_payload['result']['request']['query']}"
                )
                # print("session payload", session_payload)
                # print("metric payload", metric_payload)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    main()
