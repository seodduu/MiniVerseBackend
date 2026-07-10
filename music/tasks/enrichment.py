"""
GraphRAG 강화 수집 태스크: 무드 태그(valence/arousal 역산 포함) + 곡–곡 유사 엣지.
"""
import logging
from celery import shared_task

from ..models import Music, Tags, MusicTags, MusicSimilar
from ..services.external.lastfm import LastfmService
from ..services.internal.mood_lexicon import derive_valence_arousal

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def fetch_mood_tags_task(self, music_id: int, artist_name: str, track_name: str):
    music = Music.objects.filter(music_id=music_id, is_deleted=False).first()
    if not music:
        return None
    try:
        tags = LastfmService.get_track_top_tags(artist_name, track_name)  # [(key,count)]
        if not tags:
            tags = LastfmService.get_artist_top_tags(artist_name)  # 트랙 태그 없으면 아티스트 태그로 폴백
        scored = []
        for key, count in tags:
            score = max(min(count / 100.0, 1.0), 0.0)
            tag, _ = Tags.objects.get_or_create(
                tag_key=key, defaults={"tag_type": "mood"})
            MusicTags.objects.update_or_create(
                music=music, tag=tag, defaults={"score": score})
            scored.append((key, score))

        valence, arousal = derive_valence_arousal(scored)
        music.valence = valence
        music.arousal = arousal
        music.save(update_fields=["valence", "arousal", "updated_at"])
        return music_id
    except Exception as e:
        logger.error(f"[무드 태그] 실패 music_id={music_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)
        return None


@shared_task(bind=True, max_retries=2)
def fetch_similar_tracks_task(self, music_id: int, artist_name: str, track_name: str):
    music = Music.objects.filter(music_id=music_id, is_deleted=False).first()
    if not music:
        return None
    try:
        similar = LastfmService.get_track_similar(artist_name, track_name)
        linked = 0
        for a_name, t_name, match in similar:
            target = Music.objects.filter(
                music_name__iexact=t_name,
                artist__artist_name__iexact=a_name,
                is_deleted=False,
            ).first()
            if target and target.music_id != music.music_id:
                MusicSimilar.objects.update_or_create(
                    music=music, similar_music=target, defaults={"match": match})
                linked += 1
        return linked
    except Exception as e:
        logger.error(f"[유사곡] 실패 music_id={music_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)
        return None
