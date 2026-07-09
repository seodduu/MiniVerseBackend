from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

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


def make_authed_user(email):
    u = Users.objects.create(
        email=email, nickname=email.split('@')[0],
        created_at=timezone.now(), updated_at=timezone.now(), is_deleted=False,
    )
    u.is_authenticated = True
    return u


class GenerateAsyncJobTest(TestCase):
    def setUp(self):
        self.user = make_authed_user('gen@example.com')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch('music.tasks.generate_music_task.delay')
    def test_creates_job_and_returns_job_id(self, mock_delay):
        mock_delay.return_value.id = 'celery-task-123'
        res = self.client.post('/api/v1/music/generate-async/',
                               {'prompt': '여름 밤 드라이브', 'make_instrumental': False},
                               format='json')
        self.assertEqual(res.status_code, 202)
        self.assertIn('job_id', res.data)
        job = GenerationJob.objects.get(pk=res.data['job_id'])
        self.assertEqual(job.user_id, self.user.user_id)
        self.assertEqual(job.phase, GenerationJob.PHASE_GENERATING)
        self.assertEqual(job.celery_task_id, 'celery-task-123')
        mock_delay.assert_called_once()
        self.assertEqual(mock_delay.call_args.kwargs.get('job_id'), job.job_id)

    @patch('music.tasks.generate_music_task.delay')
    def test_rejects_second_active_job_with_409(self, mock_delay):
        mock_delay.return_value.id = 'celery-task-abc'
        GenerationJob.objects.create(user=self.user, original_prompt='이미 진행중',
                                     phase=GenerationJob.PHASE_GENERATING)
        res = self.client.post('/api/v1/music/generate-async/',
                               {'prompt': '두번째', 'make_instrumental': False},
                               format='json')
        self.assertEqual(res.status_code, 409)

    def test_requires_authentication(self):
        anon = APIClient()
        res = anon.post('/api/v1/music/generate-async/',
                        {'prompt': 'x', 'make_instrumental': False}, format='json')
        self.assertIn(res.status_code, (401, 403))
