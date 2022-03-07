from django.db import models
from django.db.models import Index
from django.utils import timezone

from sentry.db.models.base import BaseModel
from sentry.db.models.fields.array import ArrayField
from sentry.db.models.fields.foreignkey import FlexibleForeignKey


class ReplaySession(BaseModel):
    __include_in_export__ = False

    project = FlexibleForeignKey("sentry.Project")
    # TODO: index on session id
    session_id = models.CharField(max_length=64)
    sentry_event_ids = ArrayField()
    date_added = models.DateTimeField(default=timezone.now, null=True)

    class Meta:
        app_label = "replay"
        indexes = [Index(fields=["session_id"])]


# based off of nodestore model


class ReplayData(BaseModel):
    __include_in_export__ = False

    data = models.TextField()
    replay_session = FlexibleForeignKey("replay.ReplaySession")
    date_added = models.DateTimeField(default=timezone.now, null=True)

    class Meta:
        app_label = "replay"
