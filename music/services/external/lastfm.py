"""
Last.fm API 통합 서비스. 무드 태그(track.getTopTags)와 곡–곡 유사(track.getSimilar).
"""
import logging
from typing import List, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class LastfmService:
    API_URL = "https://ws.audioscrobbler.com/2.0/"
    TIMEOUT = 5

    MOOD_WHITELIST = {
        "happy", "upbeat", "positive", "uplifting", "feel good", "energetic",
        "chill", "mellow", "melancholic", "sad", "romantic", "dreamy", "dark",
        "calm", "party",
    }

    @classmethod
    def _get(cls, method: str, artist: str, track: str) -> dict:
        api_key = settings.LASTFM_API_KEY
        if not api_key:
            logger.error("[Last.fm] API_KEY 미설정")
            return {}
        try:
            r = requests.get(cls.API_URL, params={
                "method": method, "artist": artist, "track": track,
                "api_key": api_key, "format": "json", "autocorrect": 1,
            }, timeout=cls.TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[Last.fm] {method} 실패: {e}")
            return {}

    @classmethod
    def get_track_top_tags(cls, artist: str, track: str) -> List[Tuple[str, int]]:
        data = cls._get("track.getTopTags", artist, track)
        tags = (data.get("toptags", {}) or {}).get("tag", []) or []
        out = []
        for t in tags:
            key = (t.get("name", "") or "").strip().lower()
            if key in cls.MOOD_WHITELIST:
                try:
                    out.append((key, int(t.get("count", 0))))
                except (TypeError, ValueError):
                    out.append((key, 0))
        return out

    @classmethod
    def get_track_similar(cls, artist: str, track: str) -> List[Tuple[str, str, float]]:
        data = cls._get("track.getSimilar", artist, track)
        tracks = (data.get("similartracks", {}) or {}).get("track", []) or []
        out = []
        for t in tracks:
            name = t.get("name", "") or ""
            a = (t.get("artist", {}) or {}).get("name", "") or ""
            try:
                match = float(t.get("match", 0.0))
            except (TypeError, ValueError):
                match = 0.0
            if name and a:
                out.append((a, name, match))
        return out
