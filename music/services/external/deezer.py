"""
Deezer Public API 통합 서비스 (인증 불필요).
검색·메타데이터·앨범 커버·아티스트 이미지·ISRC·프리뷰 수집.
"""
import logging
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class DeezerService:
    API_BASE = "https://api.deezer.com"
    TIMEOUT = 5

    @classmethod
    def _parse_track(cls, t: Dict) -> Dict:
        artist = t.get("artist", {}) or {}
        album = t.get("album", {}) or {}
        return {
            "deezer_id": str(t.get("id", "")),
            "music_name": t.get("title", ""),
            "artist_name": artist.get("name", ""),
            "artist_deezer_id": str(artist.get("id", "")),
            "artist_image": artist.get("picture_xl", "") or "",
            "album_name": album.get("title", ""),
            "album_deezer_id": str(album.get("id", "")),
            "album_image": album.get("cover_xl", "") or "",
            "isrc": t.get("isrc", "") or "",
            "duration": t.get("duration"),
            "preview_url": t.get("preview", "") or "",
            "release_date": t.get("release_date", "") or "",  # /track/{id}에서만 제공
            "deezer_url": t.get("link", "") or "",
        }

    @classmethod
    def search_tracks(cls, term: str, limit: int = 10) -> List[Dict]:
        try:
            r = requests.get(
                f"{cls.API_BASE}/search",
                params={"q": term, "limit": limit},
                timeout=cls.TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                logger.error(f"[Deezer] 검색 실패: {data['error']}")
                return []
            items = data.get("data", []) or []
            return [cls._parse_track(t) for t in items]
        except requests.exceptions.RequestException as e:
            logger.error(f"[Deezer] 검색 실패: {e}")
            return []

    @classmethod
    def get_track(cls, deezer_id: str) -> Optional[Dict]:
        try:
            r = requests.get(
                f"{cls.API_BASE}/track/{deezer_id}",
                timeout=cls.TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                logger.error(f"[Deezer] 트랙 조회 실패: {data['error']}")
                return None
            return cls._parse_track(data)
        except requests.exceptions.RequestException as e:
            logger.error(f"[Deezer] 트랙 조회 실패: {e}")
            return None
