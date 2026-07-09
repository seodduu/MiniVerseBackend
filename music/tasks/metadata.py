"""
아티스트 이미지 + 장르 노드 수집 (Spotify 공식 API).
이미지 파일은 저장하지 않고 Spotify CDN URL 문자열만 DB에 보관(핫링크).
"""
import logging
from celery import shared_task
from django.utils import timezone

from ..models import Artists, Genres, ArtistGenres
from ..services.external.spotify import SpotifyService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def fetch_artist_image_task(self, artist_id: int, artist_spotify_id: str, artist_name: str):
    artist = Artists.objects.filter(artist_id=artist_id, is_deleted=False).first()
    if not artist:
        return None
    if not artist_spotify_id:
        logger.info(f"[아티스트 이미지] spotify_id 없음: artist_id={artist_id}")
        return None
    try:
        data = SpotifyService.get_artist(artist_spotify_id)
        image = data.get("artist_image", "")
        if image:
            artist.artist_image = image
            artist.image_large_circle = image
            artist.image_small_circle = image
            artist.image_square = image
            artist.updated_at = timezone.now()
            artist.save()

        for genre_name in data.get("genres", []):
            genre, _ = Genres.objects.get_or_create(genre_name=genre_name)
            ArtistGenres.objects.get_or_create(artist=artist, genre=genre)
        return image or None
    except Exception as e:
        logger.error(f"[아티스트 이미지] 실패 artist_id={artist_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)
        return None
