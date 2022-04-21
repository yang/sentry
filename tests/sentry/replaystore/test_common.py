"""
Testsuite of backend-independent nodestore tests. Add your backend to the
`ns` fixture to have it tested.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest

from sentry.replaystore.base import ReplayDataType
from sentry.replaystore.django.backend import DjangoReplayStore
from tests.sentry.replaystore.bigtable.tests import get_temporary_bigtable_replaystore


@contextmanager
def nullcontext(returning):
    # TODO: Replace with ``contextlib.nullcontext`` after upgrading to 3.7
    yield returning


@pytest.fixture(params=["bigtable-real", pytest.param("django", marks=pytest.mark.django_db)])
def rs(request):
    # backends are returned from context managers to support teardown when required
    backends = {
        # "bigtable-mocked": lambda: nullcontext(MockedBigtableNodeStorage(project="test")),
        "bigtable-real": lambda: get_temporary_bigtable_replaystore(),
        "django": lambda: nullcontext(DjangoReplayStore()),
    }

    ctx = backends[request.param]()
    with ctx as rs:
        rs.bootstrap()
        yield rs


def test_set(rs):
    root_replay_id = "d2502ebbd7df41ceba8d3275595cac33"
    set_data = (
        (
            root_replay_id,
            {"foo": "bar"},
            ReplayDataType.ROOT,
            datetime.now() - timedelta(seconds=10),
        ),
        (
            root_replay_id,
            {"test": "test"},
            ReplayDataType.EVENT,
            datetime.now() - timedelta(seconds=5),
        ),
        (
            root_replay_id,
            {"recording": "demo"},
            ReplayDataType.RECORDING,
            datetime.now() - timedelta(seconds=3),
        ),
    )

    for id, data, type, timestamp in set_data:
        rs.set(id, data, type, timestamp)

    replay = rs.get_replay(root_replay_id)

    assert replay.id == set_data[0][0]
    assert replay.root == set_data[0][1]
    assert replay.events == [set_data[1][1]]
    assert replay.recordings == [set_data[2][1]]


# def test_get_replay(ns):
#     nodes = [("a" * 32, {"foo": "a"}), ("b" * 32, {"foo": "b"})]

#     ns.set(nodes[0][0], nodes[0][1])
#     ns.set(nodes[1][0], nodes[1][1])

#     result = ns.get_multi([nodes[0][0], nodes[1][0]])
#     assert result == {n[0]: n[1] for n in nodes}
