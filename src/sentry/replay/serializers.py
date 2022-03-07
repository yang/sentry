from typing import Any, Mapping, MutableMapping

from sentry.api.serializers import Serializer
from sentry.api.serializers.base import register
from sentry.replay.models import ReplayData, ReplaySession
from sentry.utils import json
from sentry.utils.json import JSONData


@register(ReplayData)
class ReplayDataSerializer(Serializer):
    def serialize(
        self, obj: ReplaySession, attrs: Mapping[Any, Any], user: Any, **kwargs: Any
    ) -> MutableMapping[str, JSONData]:
        return {"dateAdded": obj.date_added, "data": obj.data}


@register(ReplaySession)
class ReplaySessionSerializer(Serializer):
    # def get_attrs(self, item_list, user, **kwargs):
    #     # prefetch_related_objects(item_list, "alert_rule")

    #     replay_session = {item.id: item for item in item_list}

    #     result = defaultdict(dict)

    #     replay_datas = ReplayData.objects.filter(replay__in=item_list).order_by("id")
    #     serialized_actions = serialize(list(replay_datas), **kwargs)
    #     for replay_data, serialized in zip(replay_datas, serialized_actions):
    #         triggers_actions = result[triggers[trigger.alert_rule_trigger_id]].setdefault(
    #             "actions", []
    #         )
    #         triggers_actions.append(serialized)

    #     return result

    def serialize(
        self, obj: ReplaySession, attrs: Mapping[Any, Any], user: Any, **kwargs: Any
    ) -> MutableMapping[str, JSONData]:

        replay_session_datas = ReplayData.objects.filter(replay_session=obj).order_by("id")

        # TODO: serializer for datas
        serialized_session_data = [json.loads(d.data) for d in replay_session_datas]

        return {"id": obj.id, "sentryEvents": obj.sentry_event_ids, "data": serialized_session_data}
