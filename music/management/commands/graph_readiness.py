"""
GraphRAG 준비 상태 리포트

사용법:
    python manage.py graph_readiness

music/tag/엣지 카운트를 집계해 GraphRAG 파이프라인이 최소한의 데이터를
갖췄는지(`ready`) 확인한다. 곡이 있고, 태그가 있고, 곡-태그 엣지가 있으면
`ready=true`.
"""
from django.core.management.base import BaseCommand
from music.models import Music, Tags, MusicTags, MusicSimilar


class Command(BaseCommand):
    help = "GraphRAG 준비 상태 리포트"

    def handle(self, *args, **opts):
        music_count = Music.objects.count()
        tag_count = Tags.objects.count()
        edge_count = MusicTags.objects.count()
        try:
            similar_count = MusicSimilar.objects.count()
        except Exception:
            similar_count = 0
        with_images = Music.objects.exclude(album__album_image="").filter(
            album__isnull=False).count()
        ready = music_count > 0 and tag_count > 0 and edge_count > 0
        self.stdout.write(
            f"music_count={music_count}\n"
            f"tag_count={tag_count}\n"
            f"music_tag_edge_count={edge_count}\n"
            f"music_similar_edge_count={similar_count}\n"
            f"tracks_with_images={with_images}\n"
            f"ready={'true' if ready else 'false'}"
        )
