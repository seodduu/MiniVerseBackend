"""
상세 조회 뷰(MusicDetailView) 테스트 - deezer_id 기준 전환 검증
"""
from unittest.mock import patch
import pytest
from rest_framework.test import APIClient
from music.models import Music


@pytest.mark.django_db
def test_detail_returns_no_lyrics_field():
    """DB에 이미 있는 곡은 deezer_id로 바로 조회되고, 응답에 lyrics 필드가 없어야 한다."""
    m = Music.objects.create(music_name="Super Shy", deezer_id="dz1",
                              audio_url="https://cdns-preview.dzcdn.net/stream/preview.mp3",
                              is_deleted=False)
    client = APIClient()
    resp = client.get(f"/api/v1/tracks/{m.deezer_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "lyrics" not in body
    assert body["audio_url"] == "https://cdns-preview.dzcdn.net/stream/preview.mp3"
    assert body["deezer_id"] == "dz1"
    assert body["deezer_url"] == "https://www.deezer.com/track/dz1"


@pytest.mark.django_db
def test_detail_not_in_db_fetches_from_deezer_and_triggers_save():
    """DB에 없으면 DeezerService.get_track 호출 후 저장 태스크를 트리거하고 202를 반환한다."""
    track = {
        "deezer_id": "dz2",
        "music_name": "Cupid",
        "artist_name": "Fifty Fifty",
        "artist_deezer_id": "art2",
        "artist_image": "",
        "album_name": "The Beginning: Cupid",
        "album_deezer_id": "alb2",
        "album_image": "",
        "isrc": "",
        "duration": 174,
        "preview_url": "https://cdns-preview.dzcdn.net/stream/cupid.mp3",
        "release_date": "",
        "deezer_url": "https://www.deezer.com/track/dz2",
    }
    client = APIClient()
    with patch("music.views.music.DeezerService.get_track", return_value=track) as mock_get_track, \
         patch("music.views.music.save_deezer_track_to_db_task.delay") as mock_delay:
        resp = client.get("/api/v1/tracks/dz2")

    assert resp.status_code == 202
    mock_get_track.assert_called_once_with("dz2")
    mock_delay.assert_called_once_with(track)
    body = resp.json()
    assert "lyrics" not in body
    assert body["deezer_id"] == "dz2"
    assert body["audio_url"] == "https://cdns-preview.dzcdn.net/stream/cupid.mp3"


@pytest.mark.django_db
def test_detail_not_found_returns_404():
    client = APIClient()
    with patch("music.views.music.DeezerService.get_track", return_value=None):
        resp = client.get("/api/v1/tracks/does-not-exist")
    assert resp.status_code == 404
