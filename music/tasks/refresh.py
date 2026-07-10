"""
30일 지난 곡 메타데이터(무드 태그·유사곡) 재수집 — Spotify/Last.fm 신선도 조항 대응.
"""
import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

from ..models import Music
from .enrichment import fetch_mood_tags_task, fetch_similar_tracks_task

logger = logging.getLogger(__name__)


@shared_task(name="music.tasks.refresh_stale_music")
def refresh_stale_music_task(days: int = 30):
    cutoff = timezone.now() - timedelta(days=days)
    stale = Music.objects.filter(updated_at__lt=cutoff, is_deleted=False)
    count = 0
    for m in stale.iterator():
        artist_name = m.artist.artist_name if m.artist else ""
        fetch_mood_tags_task.delay(m.music_id, artist_name, m.music_name)
        fetch_similar_tracks_task.delay(m.music_id, artist_name, m.music_name)
        count += 1
    logger.info(f"[refresh] {count}곡 재수집 트리거")
    return count
