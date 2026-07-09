import responses
from django.test import override_settings

from music.services.external.lastfm import LastfmService

TAGS_BODY = {"toptags": {"tag": [
    {"name": "happy", "count": 100},
    {"name": "kpop", "count": 90},          # 장르 → 화이트리스트 아님
    {"name": "upbeat", "count": 40},
    {"name": "seen live", "count": 5},       # 잡음
]}}

SIMILAR_BODY = {"similartracks": {"track": [
    {"name": "I AM", "match": "1.0", "artist": {"name": "IVE"}},
    {"name": "Spicy", "match": "0.87", "artist": {"name": "aespa"}},
]}}


@override_settings(LASTFM_API_KEY='dummy_key')
@responses.activate
def test_get_track_top_tags_filters_whitelist():
    responses.add(responses.GET, "https://ws.audioscrobbler.com/2.0/",
                  json=TAGS_BODY, status=200)
    out = LastfmService.get_track_top_tags("NewJeans", "Super Shy")
    keys = {k for k, _ in out}
    assert keys == {"happy", "upbeat"}
    assert ("happy", 100) in out


@override_settings(LASTFM_API_KEY='dummy_key')
@responses.activate
def test_get_track_similar_parses_match():
    responses.add(responses.GET, "https://ws.audioscrobbler.com/2.0/",
                  json=SIMILAR_BODY, status=200)
    out = LastfmService.get_track_similar("NewJeans", "Super Shy")
    assert ("IVE", "I AM", 1.0) in out
    assert ("aespa", "Spicy", 0.87) in out
