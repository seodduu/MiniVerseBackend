"""
Last.fm API 통합 서비스. 무드 태그(track.getTopTags)와 곡–곡 유사(track.getSimilar).
"""
import logging
from typing import List, Tuple

import requests
from django.conf import settings

from ..internal.mood_lexicon import MOOD_COORDS

logger = logging.getLogger(__name__)


class LastfmService:
    API_URL = "https://ws.audioscrobbler.com/2.0/"
    TIMEOUT = 5

    MOOD_WHITELIST = set(MOOD_COORDS)

    @classmethod
    def _get(cls, method: str, params: dict) -> dict:
        api_key = settings.LASTFM_API_KEY
        if not api_key:
            logger.error("[Last.fm] API_KEY 미설정")
            return {}
        try:
            r = requests.get(cls.API_URL, params={
                "method": method,
                "api_key": api_key, "format": "json", "autocorrect": 1,
                **params,
            }, timeout=cls.TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[Last.fm] {method} 실패: {e}")
            return {}

    @classmethod
    def _get_track(cls, method: str, artist: str, track: str) -> dict:
        return cls._get(method, {"artist": artist, "track": track})

    @classmethod
    def _get_artist(cls, method: str, artist: str) -> dict:
        return cls._get(method, {"artist": artist})

    @classmethod
    def _parse_mood_tags(cls, data: dict) -> List[Tuple[str, int]]:
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
    def get_track_top_tags(cls, artist: str, track: str) -> List[Tuple[str, int]]:
        data = cls._get_track("track.getTopTags", artist, track)
        return cls._parse_mood_tags(data)

    @classmethod
    def get_artist_top_tags(cls, artist: str) -> List[Tuple[str, int]]:
        data = cls._get_artist("artist.getTopTags", artist)
        return cls._parse_mood_tags(data)

    @classmethod
    def get_tag_top_tracks(cls, tag: str, limit: int = 50) -> List[Tuple[str, str]]:
        """무드 태그의 상위 트랙(tag.getTopTracks). 확립되고 태그가 풍부한 트랙 후보를 얻기 위한
        시드 소스 — 신곡/차트곡은 Last.fm 태그가 희박해 GraphRAG 클러스터링에 적합하지 않다."""
        data = cls._get("tag.getTopTracks", {"tag": tag, "limit": limit})
        tracks = (data.get("tracks", {}) or {}).get("track", []) or []
        out = []
        for t in tracks:
            name = t.get("name", "") or ""
            a = (t.get("artist", {}) or {}).get("name", "") or ""
            if name and a:
                out.append((a, name))
        return out

    @classmethod
    def get_track_similar(cls, artist: str, track: str) -> List[Tuple[str, str, float]]:
        data = cls._get_track("track.getSimilar", artist, track)
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
