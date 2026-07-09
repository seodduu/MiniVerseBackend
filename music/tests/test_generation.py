from django.test import TestCase
from django.utils import timezone

from music.models import GenerationJob, Users


class GenerationJobModelTest(TestCase):
    def setUp(self):
        self.user = Users.objects.create(
            email='gjt@example.com', nickname='gjt', password='test-password-hash',
            created_at=timezone.now(), updated_at=timezone.now(), is_deleted=False,
        )

    def test_defaults_to_generating_phase(self):
        job = GenerationJob.objects.create(user=self.user, original_prompt='여름 밤')
        self.assertEqual(job.phase, GenerationJob.PHASE_GENERATING)
        self.assertIn(job.phase, GenerationJob.ACTIVE_PHASES)
        self.assertIsNone(job.music)

    def test_active_phases_constant(self):
        self.assertEqual(
            GenerationJob.ACTIVE_PHASES,
            [GenerationJob.PHASE_GENERATING, GenerationJob.PHASE_PREPARING],
        )
