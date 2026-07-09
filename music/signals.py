"""
Django Signals for user setup

사용자가 회원가입하면 자동으로 기본 플레이리스트를 생성합니다.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from .models import Users, Playlists

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Users)
def create_default_playlist(sender, instance, created, **kwargs):
    """
    사용자가 회원가입하면 자동으로 "나의 좋아요 목록록" 플레이리스트를 생성
    
    - 회원가입 시에만 실행 (created=True)
    - 제목: "좋아요 표시한 음악"
    - visibility: private
    - 생성자: 회원가입한 사용자
    """
    # 신규 사용자가 아니면 스킵
    if not created:
        return
    
    # transaction 밖에서 실행되도록 on_commit 사용
    def create_playlist():
        try:
            # DB에서 최신 데이터 다시 조회 (트랜잭션 안전성)
            try:
                user = Users.objects.get(user_id=instance.user_id)
            except Users.DoesNotExist:
                logger.error(f"[Signal] 사용자를 찾을 수 없음: user_id={instance.user_id}")
                return
            
            # 기본 플레이리스트 생성
            now = timezone.now()
            playlist = Playlists.objects.create(
                user=user,
                title="나의 좋아요 목록",
                visibility="system",
                created_at=now,
                updated_at=now,
                is_deleted=False
            )
            
            logger.info(f"[Signal] 기본 플레이리스트 생성 완료: user_id={user.user_id}, "
                       f"playlist_id={playlist.playlist_id}, email={user.email}")
            
        except Exception as e:
            logger.error(f"[Signal] 기본 플레이리스트 생성 실패: user_id={instance.user_id}, 오류: {e}")
    
    # DB transaction이 완료된 후 실행
    transaction.on_commit(create_playlist)
