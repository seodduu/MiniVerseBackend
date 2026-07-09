import responses
from music.services.external.itunes import iTunesService


@responses.activate
def test_search_preview_returns_preview():
    responses.add(
        responses.GET, "https://itunes.apple.com/search",
        json={"resultCount": 1, "results": [
            {"wrapperType": "track", "kind": "song",
             "trackName": "Super Shy", "artistName": "NewJeans",
             "previewUrl": "https://audio.itunes/preview.m4a"}]},
        status=200,
    )
    assert iTunesService.search_preview("NewJeans", "Super Shy") == "https://audio.itunes/preview.m4a"


@responses.activate
def test_search_preview_no_match_returns_empty():
    responses.add(responses.GET, "https://itunes.apple.com/search",
                  json={"resultCount": 0, "results": []}, status=200)
    assert iTunesService.search_preview("Nobody", "No Such Song") == ""


@responses.activate
def test_search_preview_missing_url_returns_empty():
    responses.add(
        responses.GET, "https://itunes.apple.com/search",
        json={"resultCount": 1, "results": [
            {"wrapperType": "track", "kind": "song", "trackName": "X"}]},
        status=200,
    )
    assert iTunesService.search_preview("A", "X") == ""
