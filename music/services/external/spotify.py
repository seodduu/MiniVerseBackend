"""
Spotify Web API 통합 서비스 (Client Credentials).
검색·메타데이터·앨범 커버·아티스트 이미지·장르·ISRC 수집.
"""
import base64
import time
import logging
from typing import Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SpotifyService:
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    API_BASE = "https://api.spotify.com/v1"
    TIMEOUT = 5

    _token: Optional[str] = None
    _token_expires_at: float = 0.0

    @classmethod
    def _get_token(cls) -> Optional[str]:
        if cls._token and time.time() < cls._token_expires_at - 60:
            return cls._token
        client_id = settings.SPOTIFY_CLIENT_ID
        client_secret = settings.SPOTIFY_CLIENT_SECRET
        if not client_id or not client_secret:
            logger.error("[Spotify] CLIENT_ID/SECRET 미설정")
            return None
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        try:
            r = requests.post(
                cls.TOKEN_URL,
                data={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {auth}"},
                timeout=cls.TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            cls._token = data["access_token"]
            cls._token_expires_at = time.time() + data.get("expires_in", 3600)
            return cls._token
        except requests.exceptions.RequestException as e:
            logger.error(f"[Spotify] 토큰 발급 실패: {e}")
            return None

    @classmethod
    def _headers(cls) -> Optional[Dict]:
        token = cls._get_token()
        return {"Authorization": f"Bearer {token}"} if token else None

    @staticmethod
    def _pick_image(images: List[Dict], height: int) -> str:
        for img in images or []:
            if img.get("height") == height:
                return img.get("url", "")
        return (images[0].get("url", "") if images else "")

    @classmethod
    def _parse_track(cls, t: Dict) -> Dict:
        album = t.get("album", {}) or {}
        images = album.get("images", []) or []
        artists = t.get("artists", []) or [{}]
        first_artist = artists[0] if artists else {}
        duration_ms = t.get("duration_ms")
        return {
            "spotify_id": t.get("id", ""),
            "music_name": t.get("name", ""),
            "artist_name": first_artist.get("name", ""),
            "artist_spotify_id": first_artist.get("id", ""),
            "album_name": album.get("name", ""),
            "album_spotify_id": album.get("id", ""),
            "album_image_640": cls._pick_image(images, 640),
            "album_image_300": cls._pick_image(images, 300),
            "album_image_64": cls._pick_image(images, 64),
            "isrc": (t.get("external_ids", {}) or {}).get("isrc", ""),
            "release_date": album.get("release_date", ""),
            "duration": int(duration_ms / 1000) if duration_ms else None,
            "spotify_url": (t.get("external_urls", {}) or {}).get("spotify", ""),
        }

    @classmethod
    def search_tracks(cls, term: str, market: str = "KR", limit: int = 10) -> List[Dict]:
        headers = cls._headers()
        if not headers:
            return []
        try:
            r = requests.get(
                f"{cls.API_BASE}/search",
                params={"q": term, "type": "track", "market": market, "limit": limit},
                headers=headers, timeout=cls.TIMEOUT,
            )
            r.raise_for_status()
            items = (r.json().get("tracks", {}) or {}).get("items", []) or []
            return [cls._parse_track(t) for t in items]
        except requests.exceptions.RequestException as e:
            logger.error(f"[Spotify] 검색 실패: {e}")
            return []

    @classmethod
    def get_track(cls, spotify_id: str) -> Optional[Dict]:
        headers = cls._headers()
        if not headers:
            return None
        try:
            r = requests.get(f"{cls.API_BASE}/tracks/{spotify_id}",
                             params={"market": "KR"}, headers=headers, timeout=cls.TIMEOUT)
            r.raise_for_status()
            return cls._parse_track(r.json())
        except requests.exceptions.RequestException as e:
            logger.error(f"[Spotify] 트랙 조회 실패: {e}")
            return None

    @classmethod
    def get_artist(cls, artist_spotify_id: str) -> Dict:
        headers = cls._headers()
        if not headers:
            return {"artist_image": "", "genres": [], "spotify_url": ""}
        try:
            r = requests.get(f"{cls.API_BASE}/artists/{artist_spotify_id}",
                             headers=headers, timeout=cls.TIMEOUT)
            r.raise_for_status()
            data = r.json()
            return {
                "artist_image": cls._pick_image(data.get("images", []), 640),
                "genres": data.get("genres", []) or [],
                "spotify_url": (data.get("external_urls", {}) or {}).get("spotify", ""),
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"[Spotify] 아티스트 조회 실패: {e}")
            return {"artist_image": "", "genres": [], "spotify_url": ""}
