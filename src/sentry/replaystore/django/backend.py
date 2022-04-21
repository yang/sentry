from __future__ import annotations

from typing import Any, Dict, List, Tuple

from sentry.replaystore.base import ReplayDataType, ReplayNotFound, ReplayStore
from sentry.replaystore.django.models import Replay
from sentry.utils.strings import compress, decompress


class DjangoReplayStore(ReplayStore):
    def _get_all_events_for_replay(
        self, key: str
    ) -> Tuple[str, Dict[Any, Any], List[Dict[Any, Any]], List[Dict[Any, Any]]]:
        data = Replay.objects.filter(id__startswith=key)
        if len(data) == 0:
            raise ReplayNotFound

        id = data[0].id.split(self.KEY_DELIMETER)[0]
        events = []
        recordings = []
        for row in data:
            replay_data_type = int(row.id.split(self.KEY_DELIMETER)[1])
            if replay_data_type == ReplayDataType.ROOT:
                root: Dict[Any, Any] = self._decode(decompress(row.data))
            if replay_data_type == ReplayDataType.EVENT:
                events.append(self._decode(decompress(row.data)))
            if replay_data_type == ReplayDataType.RECORDING:
                recordings.append(self._decode(decompress(row.data)))

        return id, root, events, recordings

    def _set_bytes(self, key: str, value: bytes) -> None:
        replay = Replay.objects.create(id=key, data=compress(value))
        replay.save()

    def bootstrap(self) -> None:
        # Nothing for Django backend to do during bootstrap
        pass
