"""
메타데이터 수집 Celery 작업 (아티스트 이미지, 앨범 이미지, 가사)
"""
import logging
from celery import shared_task
from django.utils import timezone

from ..models import Music, Artists, Albums
from ..services import WikidataService, LRCLIBService, DeezerService, LyricsOvhService
from ..services.ytmusic import YTMusicService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def fetch_artist_image_task(self, artist_id: int, artist_name: str):
    """
    아티스트 이미지를 비동기로 조회하고 DB 업데이트
    
    API 호출 순서 (fallback 체인):
    1. YouTube Music API (1차)
    2. Wikidata API (2차 fallback)
    3. Deezer API (3차 fallback)
    
    Args:
        artist_id: Artist 모델의 ID
        artist_name: 아티스트 이름
        
    Returns:
        이미지 URL 또는 None
    """
    try:
        logger.info(f"[아티스트 이미지] 조회 시작: artist_id={artist_id}, name={artist_name}")
        
        # Artist 객체 조회
        try:
            artist = Artists.objects.get(artist_id=artist_id, is_deleted=False)
        except Artists.DoesNotExist:
            logger.error(f"[아티스트 이미지] Artist를 찾을 수 없음: artist_id={artist_id}")
            return None
        
        if artist.artist_image and artist.artist_image.strip():
            logger.info(f"[아티스트 이미지] 이미 이미지가 있음: artist_id={artist_id}")
            return artist.artist_image
        
        image_url = None
        source = None
        
        # 1차: YouTube Music에서 이미지 조회
        image_url = YTMusicService.fetch_artist_image(artist_name)
        if image_url:
            source = "YouTube Music"
        
        # 2차 fallback: Wikidata에서 이미지 조회
        if not image_url:
            logger.info(f"[아티스트 이미지] YouTube Music 실패, Wikidata fallback 시도: {artist_name}")
            image_url = WikidataService.fetch_artist_image(artist_name)
            if image_url:
                source = "Wikidata"
        
        # 3차 fallback: Deezer에서 이미지 조회
        if not image_url:
            logger.info(f"[아티스트 이미지] Wikidata 실패, Deezer fallback 시도: {artist_name}")
            image_url = DeezerService.fetch_artist_image(artist_name)
            if image_url:
                source = "Deezer"
        
        if image_url:
            artist.artist_image = image_url
            artist.updated_at = timezone.now()
            artist.save(update_fields=['artist_image', 'updated_at'])
            logger.info(f"[아티스트 이미지] 원본 URL 저장 완료 ({source}): artist_id={artist_id}")
            return image_url
        else:
            logger.info(f"[아티스트 이미지] 모든 API에서 이미지를 찾지 못함: artist_id={artist_id}")
            return None
            
    except Exception as e:
        logger.error(f"[아티스트 이미지] 실패: artist_id={artist_id}, 오류: {e}")
        
        if self.request.retries < self.max_retries:
            logger.info(f"[아티스트 이미지] 재시도: {self.request.retries + 1}/{self.max_retries}")
            raise self.retry(exc=e, countdown=30)
        
        return None


@shared_task(bind=True, max_retries=2)
def fetch_album_image_task(self, album_id: int, album_name: str, album_image_url: str = None, artist_name: str = None):
    """
    앨범 이미지를 조회하고 DB에 저장
    
    API 호출 순서 (fallback 체인):
    1. YouTube Music API (1차)
    2. iTunes API (2차 fallback, album_image_url 사용)
    
    Args:
        album_id: Album 모델의 ID
        album_name: 앨범 이름
        album_image_url: 앨범 이미지 URL (iTunes fallback용, 선택사항)
        artist_name: 아티스트 이름 (YouTube Music 검색 정확도 향상용, 선택사항)
        
    Returns:
        이미지 URL 또는 None
    """
    try:
        logger.info(f"[앨범 이미지] 조회 시작: album_id={album_id}, name={album_name}")
        
        # Album 객체 조회
        try:
            album = Albums.objects.get(album_id=album_id, is_deleted=False)
        except Albums.DoesNotExist:
            logger.error(f"[앨범 이미지] Album을 찾을 수 없음: album_id={album_id}")
            return None
        
        if album.album_image and album.album_image.strip():
            logger.info(f"[앨범 이미지] 이미 이미지가 있음: album_id={album_id}")
            return album.album_image
        
        image_url = None
        source = None
        
        # artist_name이 없으면 앨범의 아티스트 정보 사용
        if not artist_name and album.artist:
            artist_name = album.artist.artist_name
        
        # 1차: YouTube Music에서 이미지 조회
        image_url = YTMusicService.fetch_album_image(album_name, artist_name)
        if image_url:
            source = "YouTube Music"
        
        # 2차 fallback: iTunes에서 받은 album_image_url 사용
        if not image_url and album_image_url:
            logger.info(f"[앨범 이미지] YouTube Music 실패, iTunes fallback 시도: {album_id}")
            image_url = album_image_url
            source = "iTunes"
        
        if not image_url:
            logger.info(f"[앨범 이미지] 모든 소스에서 이미지를 찾지 못함: album_id={album_id}")
            return None
        
        album.album_image = image_url
        album.updated_at = timezone.now()
        album.save(update_fields=['album_image', 'updated_at'])
        logger.info(f"[앨범 이미지] 원본 URL 저장 완료 ({source}): album_id={album_id}")
        return image_url
            
    except Exception as e:
        logger.error(f"[앨범 이미지] 실패: album_id={album_id}, 오류: {e}")
        
        if self.request.retries < self.max_retries:
            logger.info(f"[앨범 이미지] 재시도: {self.request.retries + 1}/{self.max_retries}")
            raise self.retry(exc=e, countdown=30)
        
        return None


@shared_task(bind=True, max_retries=2)
def fetch_lyrics_task(self, music_id: int, artist_name: str, track_name: str, duration: int = None):
    """
    가사를 비동기로 조회하고 DB 업데이트
    
    API 호출 순서 (fallback 체인):
    1. LRCLIB API (1차) - 동기화된 LRC 가사 지원
    2. lyrics.ovh API (2차 fallback) - 일반 텍스트 가사
    
    Args:
        music_id: Music 모델의 ID
        artist_name: 아티스트 이름
        track_name: 곡 이름
        duration: 곡 길이 (초 단위)
        
    Returns:
        가사 문자열 또는 None
    """
    try:
        logger.info(f"[가사 조회] 시작: music_id={music_id}, {artist_name} - {track_name}")
        
        # Music 객체 조회
        try:
            music = Music.objects.get(music_id=music_id, is_deleted=False)
        except Music.DoesNotExist:
            logger.error(f"[가사 조회] Music을 찾을 수 없음: music_id={music_id}")
            return None
        
        # 이미 가사가 있으면 스킵
        if music.lyrics and music.lyrics.strip():
            logger.info(f"[가사 조회] 이미 가사가 있음: music_id={music_id}")
            return music.lyrics
        
        lyrics = None
        source = None
        
        # 1차: LRCLIB에서 가사 조회 (동기화된 LRC 가사 우선)
        lyrics = LRCLIBService.fetch_lyrics(artist_name, track_name, duration)
        if lyrics:
            source = "LRCLIB"
        
        # 2차 fallback: lyrics.ovh에서 가사 조회
        if not lyrics:
            logger.info(f"[가사 조회] LRCLIB 실패, lyrics.ovh fallback 시도: {artist_name} - {track_name}")
            lyrics = LyricsOvhService.fetch_lyrics(artist_name, track_name)
            if lyrics:
                source = "lyrics.ovh"
        
        if lyrics:
            # DB 업데이트
            music.lyrics = lyrics
            music.updated_at = timezone.now()
            music.save()
            logger.info(f"[가사 조회] 저장 완료 ({source}): music_id={music_id}, 길이={len(lyrics)}")
            return lyrics
        else:
            logger.info(f"[가사 조회] 모든 API에서 가사를 찾지 못함: music_id={music_id}")
            return None
            
    except Exception as e:
        logger.error(f"[가사 조회] 실패: music_id={music_id}, 오류: {e}")
        
        if self.request.retries < self.max_retries:
            logger.info(f"[가사 조회] 재시도: {self.request.retries + 1}/{self.max_retries}")
            raise self.retry(exc=e, countdown=30)
        
        return None
