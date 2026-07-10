"""
외부 API 연동 서비스 패키지

- iTunes, Spotify, Last.fm 등 (공식 API)
"""

from .itunes import iTunesService
from .spotify import SpotifyService
from .lastfm import LastfmService

__all__ = [
    'iTunesService',
    'SpotifyService',
    'LastfmService',
]
