from sentry.models import File, ProjectDebugFile, ScheduledDeletion
from sentry.tasks.deletion.scheduled import run_deletion
from sentry.testutils import APITestCase, TransactionTestCase
from sentry.testutils.silo import region_silo_test


@region_silo_test
class DeleteDebugFilesTest(APITestCase, TransactionTestCase):
    def test_simple(self):
        dif = self.create_dif_file()
        dif2 = self.create_dif_file()

        # NOTE: Its great that I pass the object directly to schedule a deletion task.
        # What is this even testing? I could as well just call `.delete()` directly?
        # What I want to test is the whole machinery going through the `cleanup`
        # command, or whatever is responsible to delete auto-expired entities?
        deletion = ScheduledDeletion.schedule(dif, days=0)
        deletion.update(in_progress=True)

        with self.tasks():
            run_deletion(deletion.id)

        assert not ProjectDebugFile.objects.filter(id=dif.id).exists()
        assert not File.objects.filter(id=dif.file.id).exists()

        assert ProjectDebugFile.objects.filter(id=dif2.id).exists()
        assert File.objects.filter(id=dif2.file.id).exists()
