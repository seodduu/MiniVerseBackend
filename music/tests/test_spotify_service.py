import responses
from django.test import override_settings

from music.services.external.spotify import SpotifyService


def _mock_token():
    responses.add(
        responses.POST, "https://accounts.spotify.com/api/token",
        json={"access_token": "tok", "token_type": "Bearer", "expires_in": 3600},
        status=200,
    )


SEARCH_BODY = {
    "tracks": {"items": [{
        "id": "sp_track_1",
        "name": "Super Shy",
        "duration_ms": 154000,
        "external_ids": {"isrc": "KRA402400123"},
        "external_urls": {"spotify": "https://open.spotify.com/track/sp_track_1"},
        "artists": [{"id": "sp_artist_1", "name": "NewJeans"}],
        "album": {
            "id": "sp_album_1", "name": "Get Up", "release_date": "2023-07-21",
            "images": [
                {"height": 640, "width": 640, "url": "https://i.scdn.co/image/640"},
                {"height": 300, "width": 300, "url": "https://i.scdn.co/image/300"},
                {"height": 64, "width": 64, "url": "https://i.scdn.co/image/64"},
            ],
        },
    }]}
}


@override_settings(SPOTIFY_CLIENT_ID='dummy_id', SPOTIFY_CLIENT_SECRET='dummy_secret')
@responses.activate
def test_search_tracks_parses_first_item():
    SpotifyService._token = None
    _mock_token()
    responses.add(responses.GET, "https://api.spotify.com/v1/search",
                  json=SEARCH_BODY, status=200)
    out = SpotifyService.search_tracks("newjeans super shy", limit=1)
    assert len(out) == 1
    item = out[0]
    assert item["spotify_id"] == "sp_track_1"
    assert item["music_name"] == "Super Shy"
    assert item["artist_name"] == "NewJeans"
    assert item["artist_spotify_id"] == "sp_artist_1"
    assert item["album_image_640"] == "https://i.scdn.co/image/640"
    assert item["isrc"] == "KRA402400123"
    assert item["release_date"] == "2023-07-21"
    assert item["duration"] == 154
    assert item["spotify_url"] == "https://open.spotify.com/track/sp_track_1"


@override_settings(SPOTIFY_CLIENT_ID='dummy_id', SPOTIFY_CLIENT_SECRET='dummy_secret')
@responses.activate
def test_get_artist_returns_image_and_genres():
    SpotifyService._token = None
    _mock_token()
    responses.add(
        responses.GET, "https://api.spotify.com/v1/artists/sp_artist_1",
        json={"id": "sp_artist_1", "genres": ["k-pop", "dance pop"],
              "images": [{"height": 640, "url": "https://i.scdn.co/artist/640"}],
              "external_urls": {"spotify": "https://open.spotify.com/artist/sp_artist_1"}},
        status=200,
    )
    out = SpotifyService.get_artist("sp_artist_1")
    assert out["artist_image"] == "https://i.scdn.co/artist/640"
    assert out["genres"] == ["k-pop", "dance pop"]
