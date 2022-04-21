from sentry.replaystore.base import ReplayStore

# from sentry.utils.kvstore.bigtable import BigtableKVStorage


class BigTableReplayStore(ReplayStore):
    def get(self, key):
        pass

    def set(self, key, subkey, data):
        pass
