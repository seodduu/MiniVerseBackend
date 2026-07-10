import responses

from music.services.external.deezer import DeezerService


SEARCH_BODY = {
    "data": [
        {
            "id": 3135556,
            "title": "Super Shy",
            "duration": 154,
            "isrc": "KRA402400123",
            "preview": "https://cdns-preview.dzcdn.net/stream/preview.mp3",
            "link": "https://www.deezer.com/track/3135556",
            "artist": {
                "id": 12345,
                "name": "NewJeans",
                "picture_xl": "https://api.deezer.com/artist/12345/image?xl",
            },
            "album": {
                "id": 67890,
                "title": "Get Up",
                "cover_xl": "https://api.deezer.com/album/67890/image?xl",
            },
        }
    ]
}

TRACK_BODY = {
    "id": 3135556,
    "title": "Super Shy",
    "duration": 154,
    "isrc": "KRA402400123",
    "preview": "https://cdns-preview.dzcdn.net/stream/preview.mp3",
    "link": "https://www.deezer.com/track/3135556",
    "release_date": "2023-07-21",
    "artist": {
        "id": 12345,
        "name": "NewJeans",
        "picture_xl": "https://api.deezer.com/artist/12345/image?xl",
    },
    "album": {
        "id": 67890,
        "title": "Get Up",
        "cover_xl": "https://api.deezer.com/album/67890/image?xl",
    },
}


@responses.activate
def test_search_tracks_parses_first_item():
    responses.add(
        responses.GET, "https://api.deezer.com/search",
        json=SEARCH_BODY, status=200,
    )
    out = DeezerService.search_tracks("newjeans super shy", limit=1)
    assert len(out) == 1
    item = out[0]
    assert item["deezer_id"] == "3135556"
    assert item["music_name"] == "Super Shy"
    assert item["artist_name"] == "NewJeans"
    assert item["artist_deezer_id"] == "12345"
    assert item["artist_image"] == "https://api.deezer.com/artist/12345/image?xl"
    assert item["album_image"] == "https://api.deezer.com/album/67890/image?xl"
    assert item["isrc"] == "KRA402400123"
    assert item["preview_url"] == "https://cdns-preview.dzcdn.net/stream/preview.mp3"
    assert item["duration"] == 154


@responses.activate
def test_get_track_returns_release_date():
    responses.add(
        responses.GET, "https://api.deezer.com/track/3135556",
        json=TRACK_BODY, status=200,
    )
    out = DeezerService.get_track("3135556")
    assert out is not None
    assert out["deezer_id"] == "3135556"
    assert out["release_date"] == "2023-07-21"


@responses.activate
def test_error_and_empty_responses():
    responses.add(
        responses.GET, "https://api.deezer.com/search",
        json={"data": []}, status=200,
    )
    assert DeezerService.search_tracks("nonexistent term xyz") == []

    responses.add(
        responses.GET, "https://api.deezer.com/track/0",
        json={"error": {"type": "DataException", "message": "no data", "code": 800}},
        status=200,
    )
    assert DeezerService.get_track("0") is None
