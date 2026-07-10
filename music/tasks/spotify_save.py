"""
Spotify 트랙을 DB에 저장하는 Celery 태스크.
- 중복 판정: spotify_id
- FK 순서: Artist → Album → Music (transaction.atomic)
- 미리듣기: ISRC로 iTunes 조회
- 저장 성공 시 아티스트 이미지·무드 태그·유사곡 태스크 트리거
"""
import logging
from datetime import datetime
from celery import shared_task
from django.utils import timezone
from django.db import transaction

from ..models import Music, Artists, Albums
from ..services.external.itunes import iTunesService
from .metadata import fetch_artist_image_task
from .enrichment import fetch_mood_tags_task, fetch_similar_tracks_task

logger = logging.getLogger(__name__)


def _parse_date(value: str):
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


@shared_task(bind=True, max_retries=3)
def save_spotify_track_to_db_task(self, track: dict):
    spotify_id = track.get("spotify_id")
    if not spotify_id:
        logger.error("[Spotify 저장] spotify_id 없음")
        return None

    existing = Music.objects.filter(spotify_id=spotify_id, is_deleted=False).first()
    if existing:
        return existing.music_id

    try:
        with transaction.atomic():
            artist = None
            artist_sid = track.get("artist_spotify_id")
            artist_name = track.get("artist_name", "")
            if artist_name:
                artist, a_created = Artists.objects.get_or_create(
                    spotify_id=artist_sid or None,
                    defaults={"artist_name": artist_name, "artist_image": ""},
                )
                if not artist.artist_name:
                    artist.artist_name = artist_name
                    artist.save()

            album = None
            album_sid = track.get("album_spotify_id")
            album_name = track.get("album_name", "")
            if album_sid:
                album, al_created = Albums.objects.get_or_create(
                    spotify_id=album_sid,
                    defaults={
                        "album_name": album_name,
                        "album_image": track.get("album_image_640", ""),
                        "image_large_square": track.get("album_image_640", ""),
                        "image_square": track.get("album_image_300", ""),
                        "release_date": _parse_date(track.get("release_date", "")),
                        "artist": artist,
                    },
                )

            preview = iTunesService.search_preview(track.get("artist_name", ""), track.get("music_name", ""))

            music = Music.objects.create(
                spotify_id=spotify_id,
                isrc=track.get("isrc", "") or None,
                music_name=track.get("music_name", ""),
                artist=artist,
                album=album,
                duration=track.get("duration"),
                audio_url=preview,
                is_ai=False,
            )

        # 후속 비동기 수집 (트랜잭션 밖)
        if artist and artist.artist_id:
            fetch_artist_image_task.delay(artist.artist_id, artist.spotify_id, artist_name)
        fetch_mood_tags_task.delay(music.music_id, artist_name, music.music_name)
        fetch_similar_tracks_task.delay(music.music_id, artist_name, music.music_name)
        return music.music_id

    except Exception as e:
        logger.error(f"[Spotify 저장] 실패 spotify_id={spotify_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=10)
        return None
