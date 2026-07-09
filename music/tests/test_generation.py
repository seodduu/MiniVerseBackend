from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from music.models import GenerationJob, Users
from music.models import Music, MusicAudioBlob
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


class AudioStreamTest(TestCase):
    def setUp(self):
        self.user = make_authed_user('audio@example.com')
        self.music = Music.objects.create(
            user=self.user, music_name='곡', is_ai=True,
            created_at=timezone.now(), updated_at=timezone.now(), is_deleted=False,
        )
        MusicAudioBlob.objects.create(
            music=self.music, content_type='audio/mpeg',
            data=b'0123456789', size=10,
        )
        self.client = APIClient()

    def test_full_get_returns_200_and_bytes(self):
        res = self.client.get(f'/api/v1/music/{self.music.music_id}/audio/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(b''.join(res.streaming_content), b'0123456789')
        self.assertEqual(res['Content-Type'], 'audio/mpeg')

    def test_range_get_returns_206_partial(self):
        res = self.client.get(f'/api/v1/music/{self.music.music_id}/audio/',
                              HTTP_RANGE='bytes=2-5')
        self.assertEqual(res.status_code, 206)
        self.assertEqual(b''.join(res.streaming_content), b'2345')
        self.assertEqual(res['Content-Range'], 'bytes 2-5/10')

    def test_missing_blob_returns_404(self):
        m2 = Music.objects.create(
            user=self.user, music_name='없음', is_ai=True,
            created_at=timezone.now(), updated_at=timezone.now(), is_deleted=False,
        )
        res = self.client.get(f'/api/v1/music/{m2.music_id}/audio/')
        self.assertEqual(res.status_code, 404)


class TaskPhaseTransitionTest(TestCase):
    def setUp(self):
        self.user = make_authed_user('phase@example.com')
        self.job = GenerationJob.objects.create(
            user=self.user, original_prompt='p', phase=GenerationJob.PHASE_GENERATING,
        )

    def test_failed_phase_set_on_music_creation_error(self):
        # user_id 없는(=None) 상태로 강제 실패 유도 대신, 존재하지 않는 흐름을 직접 검증
        from music.tasks.ai_music import _mark_job_failed
        _mark_job_failed(self.job.job_id, '테스트 실패')
        self.job.refresh_from_db()
        self.assertEqual(self.job.phase, GenerationJob.PHASE_FAILED)
        self.assertEqual(self.job.error, '테스트 실패')

    def test_preparing_helper_sets_music_and_phase(self):
        from music.tasks.ai_music import _mark_job_preparing
        music = Music.objects.create(
            user=self.user, music_name='곡', is_ai=True,
            created_at=timezone.now(), updated_at=timezone.now(), is_deleted=False,
        )
        _mark_job_preparing(self.job.job_id, music.music_id)
        self.job.refresh_from_db()
        self.assertEqual(self.job.phase, GenerationJob.PHASE_PREPARING)
        self.assertEqual(self.job.music_id, music.music_id)
