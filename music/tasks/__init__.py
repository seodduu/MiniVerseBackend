"""
Celery 비동기 작업 정의 (도메인별로 분리)
"""

# 공통/테스트 작업
from .common import (
    test_task,
)

# 메타데이터 수집 작업
from .metadata import (
    fetch_artist_image_task,
)

# AI 음악 생성 작업
from .ai_music import (
    generate_music_task,
    upload_suno_audio_to_s3_task,
    fetch_timestamped_lyrics_task,
    process_suno_webhook_task,
)

# 차트 계산 작업
from .charts import (
    update_realtime_chart,
    update_daily_chart,
    update_ai_chart,
)

# 데이터 정리 작업
from .cleanup import (
    cleanup_old_playlogs,
    cleanup_old_realtime_charts,
)

# 이미지 리사이징 작업
from .image_resize import (
    resize_image_task,
)

# GraphRAG 강화 수집 작업 (무드 태그 + 유사곡)
from .enrichment import (
    fetch_mood_tags_task,
    fetch_similar_tracks_task,
)

# Spotify 저장 작업
from .spotify_save import (
    save_spotify_track_to_db_task,
)

__all__ = [
    # 공통
    'test_task',
    # 메타데이터
    'fetch_artist_image_task',
    # AI 음악
    'generate_music_task',
    'upload_suno_audio_to_s3_task',
    'fetch_timestamped_lyrics_task',
    'process_suno_webhook_task',
    # 차트
    'update_realtime_chart',
    'update_daily_chart',
    'update_ai_chart',
    # 정리
    'cleanup_old_playlogs',
    'cleanup_old_realtime_charts',
    # 이미지 리사이징
    'resize_image_task',
    # GraphRAG 강화 수집
    'fetch_mood_tags_task',
    'fetch_similar_tracks_task',
    # Spotify 저장
    'save_spotify_track_to_db_task',
]
