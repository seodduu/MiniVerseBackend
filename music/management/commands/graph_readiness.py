"""
GraphRAG 준비 상태 리포트

사용법:
    python manage.py graph_readiness

GraphRAG의 직접 태그, 유사곡, 아티스트 장르, 무드 좌표 신호별 준비 상태와
커버리지를 확인한다. 직접 태그 그래프가 있으면 전체 검색은 ready이며,
나머지 신호는 독립적으로 degraded mode를 지원한다.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from music.models import ArtistGenres, Music, MusicSimilar, MusicTags, Tags


class Command(BaseCommand):
    help = "GraphRAG 준비 상태 리포트"

    def handle(self, *args, **opts):
        music_count = Music.objects.count()
        tag_count = Tags.objects.count()
        music_tag_count = MusicTags.objects.count()
        similar_count = MusicSimilar.objects.count()
        artist_genre_count = ArtistGenres.objects.count()
        tracks_with_tags = MusicTags.objects.values("music_id").distinct().count()
        tracks_with_similar = Music.objects.filter(
            Q(similar_from__is_deleted=False) | Q(similar_to__is_deleted=False)
        ).distinct().count()
        artist_count = (
            Music.objects.filter(artist__isnull=False)
            .values("artist_id")
            .distinct()
            .count()
        )
        artists_with_genres = ArtistGenres.objects.values("artist_id").distinct().count()
        tracks_with_mood = Music.objects.filter(
            valence__isnull=False, arousal__isnull=False
        ).count()
        invalid_mood = Music.objects.filter(
            Q(valence__lt=-1) | Q(valence__gt=1) | Q(arousal__lt=-1) | Q(arousal__gt=1)
        ).count()
        with_images = (
            Music.objects.exclude(album__album_image="")
            .filter(album__isnull=False)
            .count()
        )
        ready_direct = music_count > 0 and tag_count > 0 and music_tag_count > 0

        def ratio(numerator, denominator):
            return numerator / denominator if denominator else 0.0

        self.stdout.write(
            f"music_count={music_count}\n"
            f"tag_count={tag_count}\n"
            f"music_tag_edge_count={music_tag_count}\n"
            f"music_similar_edge_count={similar_count}\n"
            f"artist_genre_edge_count={artist_genre_count}\n"
            f"tracks_with_tags_ratio={ratio(tracks_with_tags, music_count):.4f}\n"
            f"tracks_with_similar_ratio={ratio(tracks_with_similar, music_count):.4f}\n"
            f"artists_with_genres_ratio={ratio(artists_with_genres, artist_count):.4f}\n"
            f"tracks_with_mood_coords_ratio={ratio(tracks_with_mood, music_count):.4f}\n"
            f"invalid_mood_coords_count={invalid_mood}\n"
            f"tracks_with_images={with_images}\n"
            f"ready_direct_tag={'true' if ready_direct else 'false'}\n"
            f"ready_similar={'true' if similar_count > 0 else 'false'}\n"
            f"ready_artist_genre={'true' if artist_genre_count > 0 else 'false'}\n"
            f"ready_mood={'true' if tracks_with_mood > 0 and invalid_mood == 0 else 'false'}\n"
            f"ready={'true' if ready_direct else 'false'}"
        )
