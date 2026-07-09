"""Media storage helpers backed by the local Postgres database."""
import logging
from typing import Optional

import requests
from django.utils import timezone

from music.models import MusicAudioBlob

logger = logging.getLogger(__name__)


def download_file_from_url(url: str, timeout: int = 30) -> tuple[bytes, str]:
    """Download a remote media file and return its bytes plus content type."""
    logger.info("[미디어 저장] 파일 다운로드 시작: %s", url)
    response = requests.get(url, timeout=timeout, stream=True)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type") or "application/octet-stream"
    content = response.content
    logger.info("[미디어 저장] 파일 다운로드 완료: %s bytes", len(content))
    return content, content_type


def store_audio_blob(music, data: bytes, content_type: str = "audio/mpeg") -> MusicAudioBlob:
    """Store audio bytes in Postgres for one music row."""
    blob, _ = MusicAudioBlob.objects.update_or_create(
        music=music,
        defaults={
            "content_type": content_type or "audio/mpeg",
            "data": data,
            "size": len(data),
        },
    )
    return blob


def download_and_store_audio(music, url: str, content_type: Optional[str] = None) -> MusicAudioBlob:
    """Download audio from a URL and store it in Postgres."""
    data, detected_content_type = download_file_from_url(url)
    return store_audio_blob(music, data, content_type or detected_content_type or "audio/mpeg")


def audio_api_url(music_id: int) -> str:
    """Return the local API URL used to stream a stored audio blob."""
    return f"/api/v1/tracks/{music_id}/audio/"


def is_suno_url(url: str) -> bool:
    """Return True for known Suno CDN/API media URLs."""
    if not url:
        return False

    suno_domains = [
        "cdn.suno.ai",
        "cdn1.suno.ai",
        "suno.ai",
        "sunoapi.org",
        "musicfile.api.box",
        "audiopipe.suno.ai",
    ]
    return any(domain in url for domain in suno_domains)


def touch_music_audio_url(music) -> str:
    """Point Music.audio_url at the local streaming API path."""
    url = audio_api_url(music.music_id)
    music.audio_url = url
    music.updated_at = timezone.now()
    music.save(update_fields=["audio_url", "updated_at"])
    return url
