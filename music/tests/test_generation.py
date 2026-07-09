from django.test import TestCase
from django.utils import timezone

from music.models import GenerationJob, Users
from music.serializers.generation import GenerationJobSerializer


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


class GenerationJobSerializerTest(TestCase):
    def setUp(self):
        self.user = Users.objects.create(
            email='ser@example.com', nickname='ser',
            created_at=timezone.now(), updated_at=timezone.now(), is_deleted=False,
        )

    def test_serializes_expected_keys(self):
        job = GenerationJob.objects.create(
            user=self.user, original_prompt='봄', converted_prompt='spring',
        )
        data = GenerationJobSerializer(job).data
        self.assertEqual(
            set(data.keys()),
            {'job_id', 'phase', 'music_id', 'audio_url',
             'original_prompt', 'converted_prompt', 'error'},
        )
        self.assertIsNone(data['music_id'])
        self.assertIsNone(data['audio_url'])
        self.assertEqual(data['phase'], 'generating')
