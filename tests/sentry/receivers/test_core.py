# coding: utf-8

from __future__ import absolute_import

from django.conf import settings

from sentry.models import (
    Organization, Project, ProjectKey, Team, TeamMemberType, User
)
from sentry.receivers.core import create_default_projects
from sentry.testutils import TestCase


class CreateDefaultProjectsTest(TestCase):
    def test_simple(self):
        user, _ = User.objects.get_or_create(is_superuser=True, defaults={
            'username': 'test'
        })
        Organization.objects.all().delete()
        Team.objects.filter(slug='sentry').delete()
        Project.objects.filter(id=settings.SENTRY_PROJECT).delete()

        create_default_projects(created_models=[Project])

        project = Project.objects.get(id=settings.SENTRY_PROJECT)
        assert project.public is False
        assert project.name == 'Backend'
        assert project.slug == 'backend'
        team = project.team
        assert team.owner == user
        assert team.slug == 'sentry'

        pk = ProjectKey.objects.get(project=project)
        assert not pk.roles.api
        assert pk.roles.store
        assert pk.user is None

        # ensure that we dont hit an error here
        create_default_projects(created_models=[Project])

    def test_without_user(self):
        User.objects.filter(is_superuser=True).delete()
        Team.objects.filter(slug='sentry').delete()
        Project.objects.filter(id=settings.SENTRY_PROJECT).delete()

        create_default_projects(created_models=[Project])

        user = User.objects.get(username='sentry')

        project = Project.objects.get(id=settings.SENTRY_PROJECT)
        assert project.public is False
        assert project.name == 'Backend'
        assert project.slug == 'backend'
        team = project.team
        assert team.owner == user
        assert team.slug == 'sentry'

        pk = ProjectKey.objects.get(project=project)
        assert not pk.roles.api
        assert pk.roles.store
        assert pk.user is None

        # ensure that we dont hit an error here
        create_default_projects(created_models=[Project])


class CreateTeamMemberForOwner(TestCase):
    def test_simple(self):
        user = User.objects.create(username='foo')
        team = Team.objects.create(name='foo', slug='foo', owner=user,
                                   organization=self.organization)
        assert team.member_set.filter(
            user=user,
            type=TeamMemberType.ADMIN,
        ).exists()
