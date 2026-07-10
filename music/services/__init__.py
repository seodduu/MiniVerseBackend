"""
Music 앱의 Services 패키지
외부 API 통합 및 비즈니스 로직을 제공합니다.

외부 서비스:
- iTunes, Spotify, Last.fm 등 (공식 API)

내부 서비스:
- UserStatisticsService 등 도메인 비즈니스 로직
"""

# 외부 API 서비스들
from .external.itunes import iTunesService
from .external.spotify import SpotifyService
from .external.lastfm import LastfmService

# 내부 비즈니스 로직 서비스들
from .internal.ai_music_service import AiMusicGenerationService
from .internal.user_statistics import UserStatisticsService

# 검색 엔진
from .opensearch import opensearch_service

__all__ = [
    # 외부 API 서비스들
    'iTunesService',
    'SpotifyService',
    'LastfmService',

    # 내부 비즈니스 로직
    'AiMusicGenerationService',  # AI 음악 생성
    'UserStatisticsService',     # 사용자 음악 통계

    # 검색 엔진
    'opensearch_service',        # AWS OpenSearch 검색
]
