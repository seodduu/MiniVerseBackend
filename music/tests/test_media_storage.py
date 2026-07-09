from django.test import Client, TestCase

from music.models import Music, MusicAudioBlob
from music.utils.media_storage import audio_api_url, store_audio_blob, touch_music_audio_url


class MusicAudioBlobStorageTest(TestCase):
    def setUp(self):
        self.music = Music.objects.create(
            music_name='Local audio',
            audio_url='https://cdn.suno.ai/example.mp3',
            is_ai=True,
        )

    def test_store_audio_blob_updates_one_row(self):
        blob = store_audio_blob(self.music, b'abcdef', 'audio/mpeg')

        self.assertEqual(blob.size, 6)
        self.assertEqual(blob.content_type, 'audio/mpeg')
        self.assertEqual(MusicAudioBlob.objects.count(), 1)

        updated = store_audio_blob(self.music, b'xyz', 'audio/wav')
        self.assertEqual(updated.size, 3)
        self.assertEqual(updated.content_type, 'audio/wav')
        self.assertEqual(MusicAudioBlob.objects.count(), 1)

    def test_touch_music_audio_url_points_to_streaming_endpoint(self):
        url = touch_music_audio_url(self.music)
        self.music.refresh_from_db()

        self.assertEqual(url, audio_api_url(self.music.music_id))
        self.assertEqual(self.music.audio_url, f'/api/v1/tracks/{self.music.music_id}/audio/')


class MusicAudioBlobViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.music = Music.objects.create(
            music_name='Streamed audio',
            audio_url='',
            is_ai=True,
        )
        store_audio_blob(self.music, b'abcdef', 'audio/mpeg')

    def test_streams_full_audio_blob(self):
        response = self.client.get(f'/api/v1/tracks/{self.music.music_id}/audio/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'abcdef')
        self.assertEqual(response['Content-Type'], 'audio/mpeg')
        self.assertEqual(response['Accept-Ranges'], 'bytes')

    def test_streams_range_request(self):
        response = self.client.get(
            f'/api/v1/tracks/{self.music.music_id}/audio/',
            HTTP_RANGE='bytes=1-3',
        )

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b'bcd')
        self.assertEqual(response['Content-Range'], 'bytes 1-3/6')
