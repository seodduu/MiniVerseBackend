import pytest
from unittest.mock import patch
from rest_framework.test import APIClient

DZ_RESULTS = [{
    "deezer_id": "dz1", "music_name": "Super Shy", "artist_name": "NewJeans",
    "artist_deezer_id": "dza1", "artist_image": "https://cdn-images.dzcdn.net/images/artist/xl.jpg",
    "album_name": "Get Up", "album_deezer_id": "dzal1",
    "album_image": "https://cdn-images.dzcdn.net/images/cover/xl.jpg",
    "isrc": "KR1", "duration": 154,
    "preview_url": "https://cdns-preview.dzcdn.net/stream/preview.mp3",
    "release_date": "", "deezer_url": "https://www.deezer.com/track/dz1",
}]


@pytest.mark.django_db
@patch("music.views.search.DeezerService.search_tracks", return_value=DZ_RESULTS)
def test_search_returns_deezer_shape(mock_search):
    client = APIClient()
    resp = client.get("/api/v1/search", {"q": "super shy"})
    assert resp.status_code == 200
    item = resp.json()["results"][0]
    assert item["deezer_id"] == "dz1"
    assert item["music_name"] == "Super Shy"
    assert item["artist_name"] == "NewJeans"
    assert item["album_name"] == "Get Up"
    assert item["album_image"] == "https://cdn-images.dzcdn.net/images/cover/xl.jpg"
    assert item["audio_url"] == "https://cdns-preview.dzcdn.net/stream/preview.mp3"
    assert item["isrc"] == "KR1"
    assert item["deezer_url"] == "https://www.deezer.com/track/dz1"
    assert item["in_db"] is False


@pytest.mark.django_db
def test_search_requires_q_param():
    client = APIClient()
    resp = client.get("/api/v1/search")
    assert resp.status_code == 400
