"""
외부 API 연동 서비스 패키지

- Last.fm 등 (공식 API)
"""

from .lastfm import LastfmService

__all__ = [
    'LastfmService',
]
