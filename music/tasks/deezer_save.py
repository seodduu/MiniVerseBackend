"""
Deezer 트랙을 DB에 저장하는 Celery 태스크.
- 중복 판정: deezer_id
- FK 순서: Artist → Album → Music (transaction.atomic)
- Deezer 검색/조회 응답에 아티스트 이미지, 30초 프리뷰가 이미 포함되어 있으므로
  별도의 아티스트 이미지 수집이나 iTunes 조회가 필요 없다.
- 저장 성공 시 무드 태그·유사곡 태스크(Last.fm 기반)를 트리거
"""
import logging
from datetime import datetime
from celery import shared_task
from django.db import transaction

from ..models import Music, Artists, Albums
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
def save_deezer_track_to_db_task(self, track: dict):
    deezer_id = track.get("deezer_id")
    if not deezer_id:
        logger.error("[Deezer 저장] deezer_id 없음")
        return None

    existing = Music.objects.filter(deezer_id=deezer_id, is_deleted=False).first()
    if existing:
        return existing.music_id

    try:
        with transaction.atomic():
            artist = None
            artist_did = track.get("artist_deezer_id")
            artist_name = track.get("artist_name", "")
            artist_image = track.get("artist_image", "")
            if artist_name:
                artist, a_created = Artists.objects.get_or_create(
                    deezer_id=artist_did or None,
                    defaults={
                        "artist_name": artist_name,
                        "artist_image": artist_image,
                        "image_large_circle": artist_image,
                        "image_small_circle": artist_image,
                        "image_square": artist_image,
                    },
                )
                if not artist.artist_name:
                    artist.artist_name = artist_name
                    artist.save()

            album = None
            album_did = track.get("album_deezer_id")
            album_name = track.get("album_name", "")
            album_image = track.get("album_image", "")
            if album_did:
                album, al_created = Albums.objects.get_or_create(
                    deezer_id=album_did,
                    defaults={
                        "album_name": album_name,
                        "album_image": album_image,
                        "image_large_square": album_image,
                        "image_square": album_image,
                        "release_date": _parse_date(track.get("release_date", "")),
                        "artist": artist,
                    },
                )

            music = Music.objects.create(
                deezer_id=deezer_id,
                isrc=track.get("isrc", "") or None,
                music_name=track.get("music_name", ""),
                artist=artist,
                album=album,
                duration=track.get("duration"),
                audio_url=track.get("preview_url", ""),
                is_ai=False,
            )

        # 후속 비동기 수집 (트랜잭션 밖) - Last.fm 기반 무드 태그/유사곡
        fetch_mood_tags_task.delay(music.music_id, artist_name, music.music_name)
        fetch_similar_tracks_task.delay(music.music_id, artist_name, music.music_name)
        return music.music_id

    except Exception as e:
        logger.error(f"[Deezer 저장] 실패 deezer_id={deezer_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=10)
        return None
