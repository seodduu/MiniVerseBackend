from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from music.models import Artists, Albums, Music, MusicTags, Tags


class CanvasGraphRagEmptyDataTest(TestCase):
    """음악/태그 데이터가 전혀 없을 때 캔버스 GraphRAG 엔드포인트는 명시적인 빈 상태를 반환한다."""

    def test_returns_empty_data_state_when_no_data(self):
        client = APIClient()
        resp = client.get('/api/v1/canvas/graphrag', {'tags': 'happy'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'empty_data')
        self.assertIn(
            data['meta']['data_state'],
            {'missing_music', 'missing_tags', 'missing_music_tags'},
        )


class CanvasGraphRagWithDataTest(TestCase):
    """음악-태그 데이터가 있을 때 태그 검색 결과가 relevance_score 등과 함께 반환된다."""

    def setUp(self):
        self.tag = Tags.objects.create(
            tag_key='happy', tag_type='mood',
            created_at=timezone.now(), updated_at=timezone.now(), is_deleted=False,
        )
        self.artist = Artists.objects.create(
            artist_name='테스트 아티스트',
            created_at=timezone.now(), updated_at=timezone.now(), is_deleted=False,
        )
        self.album = Albums.objects.create(
            artist=self.artist, album_name='테스트 앨범',
            image_large_square='https://example.com/large.jpg',
            created_at=timezone.now(), updated_at=timezone.now(), is_deleted=False,
        )
        self.music = Music.objects.create(
            artist=self.artist, album=self.album, music_name='테스트 곡',
            audio_url='https://example.com/preview.mp3',
            created_at=timezone.now(), updated_at=timezone.now(), is_deleted=False,
        )
        MusicTags.objects.create(
            music=self.music, tag=self.tag, score=0.9,
            created_at=timezone.now(), updated_at=timezone.now(), is_deleted=False,
        )

    def test_returns_ok_with_matched_items(self):
        client = APIClient()
        resp = client.get('/api/v1/canvas/graphrag', {'tags': 'happy'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'ok')
        self.assertGreaterEqual(len(data['items']), 1)

        item = data['items'][0]
        self.assertIn('relevance_score', item)
        self.assertIn('visual_weight', item)
        self.assertIn('matched_tags', item)
        self.assertIn('cluster', item)
        self.assertEqual(item['music_id'], self.music.music_id)
