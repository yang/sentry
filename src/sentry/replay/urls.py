from django.conf.urls import url

from sentry.replay.replay_details import ProjectReplayDetailsEndpoint
from sentry.replay.replay_index import ProjectReplayIndexEndpoint

urlpatterns = [
    url(
        r"^replays/(?P<replay_id>[^\/]+)/$",
        ProjectReplayDetailsEndpoint.as_view(),
        name="sentry-api-0-project-replay-details",
    ),
    url(
        r"^replays/$",
        ProjectReplayIndexEndpoint.as_view(),
        name="sentry-api-0-project-replay-index",
    ),
]
__all__ = ("urlpatterns",)
