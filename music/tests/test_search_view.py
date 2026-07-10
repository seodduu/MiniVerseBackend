import types
import importlib

import pytest
from unittest.mock import patch
from rest_framework.test import APIClient

# NOTE: music/views/music.py (Task 11 scope, not yet updated) still imports
# `fetch_album_image_task` / `fetch_lyrics_task`, which Task 9 removed from
# music/tasks. Importing the `music.views` package (required to reach
# `music.views.search` and to resolve the app's URLconf) transitively
# imports music/views/music.py and raises ImportError. Stub the missing
# task attributes here (test-time only, no source files touched) so this
# test can exercise the real URL route without depending on Task 11.
_tasks_module = importlib.import_module('music.tasks')
for _missing_task in ('fetch_album_image_task', 'fetch_lyrics_task'):
    if not hasattr(_tasks_module, _missing_task):
        setattr(_tasks_module, _missing_task, types.SimpleNamespace(delay=lambda *a, **k: None))

SP_RESULTS = [{
    "spotify_id": "sp1", "music_name": "Super Shy", "artist_name": "NewJeans",
    "artist_spotify_id": "spa1", "album_name": "Get Up", "album_spotify_id": "spal1",
    "album_image_640": "https://i.scdn.co/640", "album_image_300": "",
    "album_image_64": "", "isrc": "KR1", "release_date": "2023-07-21",
    "duration": 154, "spotify_url": "https://open.spotify.com/track/sp1",
}]


@pytest.mark.django_db
@patch("music.views.search.SpotifyService.search_tracks", return_value=SP_RESULTS)
def test_search_returns_spotify_shape(mock_search):
    client = APIClient()
    resp = client.get("/api/v1/search", {"q": "super shy"})
    assert resp.status_code == 200
    item = resp.json()["results"][0]
    assert item["spotify_id"] == "sp1"
    assert item["music_name"] == "Super Shy"
    assert item["artist_name"] == "NewJeans"
    assert item["album_name"] == "Get Up"
    assert item["album_image"] == "https://i.scdn.co/640"
    assert item["audio_url"] == ""
    assert item["isrc"] == "KR1"
    assert item["spotify_url"] == "https://open.spotify.com/track/sp1"
    assert item["in_db"] is False


@pytest.mark.django_db
def test_search_requires_q_param():
    client = APIClient()
    resp = client.get("/api/v1/search")
    assert resp.status_code == 400
