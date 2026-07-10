"""
GraphRAG용 실제 트랙 시드 명령어 (Deezer + Last.fm).

사용법:
    python manage.py seed_graphrag --count 100 [--db <informational label>]

설계 근거:
    GraphRAG는 조밀한 무드 클러스터와 곡-곡 유사 엣지를 필요로 한다. 신곡/차트곡은
    Last.fm 태그가 희박해 클러스터가 형성되지 않는다. 따라서 후보 트랙을 최신 차트가
    아니라 Last.fm `tag.getTopTracks`(무드 화이트리스트 태그별)에서 소싱한다 — 이
    엔드포인트는 오래되고 태그가 두텁게 쌓인("확립된") 트랙을 반환하며, 이런 트랙들은
    `track.getSimilar`로 서로 잘 연결된다.

동작 개요:
    1) Celery eager 모드 활성화 (enrichment .delay가 즉시 동기 실행되도록)
    2) MOOD_TAGS의 각 태그에 대해 tag.getTopTracks로 후보 (artist, track) 수집,
       중복 제거 후 --count 만큼으로 제한
    3) PASS 1: 각 후보를 Deezer에서 검색 → 저장 (저장 시 무드 태그도 eager로 함께 수집됨)
    4) PASS 2: 저장된 모든 트랙에 대해 실제 Last.fm 유사곡 조회 → music_similar 엣지 저장
       (모든 트랙이 이미 DB에 있어야 유사곡 매칭이 최대화되므로 별도 패스로 분리)
    5) 요약 리포트 출력
"""
import math
import time

from django.core.management.base import BaseCommand

from config.celery import app as celery_app

from music.models import Music, Tags, MusicTags, MusicSimilar
from music.services.external.deezer import DeezerService
from music.services.external.lastfm import LastfmService
from music.tasks.deezer_save import save_deezer_track_to_db_task
from music.tasks.enrichment import fetch_similar_tracks_task

MOOD_TAGS = [
    "happy", "chill", "melancholic", "energetic", "romantic",
    "sad", "dark", "dreamy", "mellow", "party",
]


class Command(BaseCommand):
    help = (
        "GraphRAG용 실제 트랙(~100곡)을 Deezer+Last.fm에서 시드한다. "
        "Last.fm tag.getTopTracks로 확립된(태그가 풍부한) 트랙을 소싱해 "
        "무드 클러스터와 곡-곡 유사 엣지를 조밀하게 만든다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=100,
            help="시드할 목표 트랙 수 (기본 100)",
        )
        parser.add_argument(
            "--db", type=str, default=None,
            help="정보용 라벨(어떤 DB에 대해 실행 중인지 로그에 남기기 위함). "
                 "실제 접속 DB는 Django SQL_DATABASE 설정을 따른다.",
        )
        parser.add_argument(
            "--page", type=int, default=1,
            help="Last.fm tag.getTopTracks 페이지 (기본 1)",
        )

    def handle(self, *args, **options):
        # Celery eager 모드: .delay() 호출이 즉시 동기 실행되도록 강제한다.
        # 이렇게 해야 워커 없이도 커맨드 프로세스 안에서 무드 태그/유사곡 수집이 끝난다.
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = False

        count = options["count"]
        page = max(options["page"], 1)
        db_label = options.get("db")
        if db_label:
            self.stdout.write(f"[seed_graphrag] target db label: {db_label}")
        self.stdout.write(f"[seed_graphrag] target count: {count}")
        self.stdout.write(f"[seed_graphrag] Last.fm candidate page: {page}")

        candidates = self._collect_candidates(count, page)
        self.stdout.write(f"[seed_graphrag] collected {len(candidates)} candidates from Last.fm mood tags")

        saved_music = self._pass1_save_and_mood(candidates)
        self.stdout.write(f"[seed_graphrag] PASS 1 done: {len(saved_music)} tracks saved")

        self._pass2_similar_edges(saved_music)
        self.stdout.write("[seed_graphrag] PASS 2 done: similar-track edges collected")

        self._print_summary()

    # ------------------------------------------------------------------
    # Candidate collection
    # ------------------------------------------------------------------
    def _collect_candidates(self, count: int, page: int = 1):
        per_tag_limit = math.ceil(count / len(MOOD_TAGS)) + 3
        seen = set()
        candidates = []
        for tag in MOOD_TAGS:
            try:
                pairs = LastfmService.get_tag_top_tracks(
                    tag, limit=per_tag_limit, page=page
                )
            except Exception as e:
                self.stderr.write(f"[seed_graphrag] tag.getTopTracks failed for '{tag}': {e}")
                continue
            for artist, track in pairs:
                key = (artist.strip().lower(), track.strip().lower())
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((artist, track))
                if len(candidates) >= count:
                    break
            self.stdout.write(f"[seed_graphrag]   tag='{tag}' -> {len(pairs)} tracks (total candidates so far: {len(candidates)})")
            if len(candidates) >= count:
                break
        return candidates[:count]

    # ------------------------------------------------------------------
    # PASS 1: Deezer search + save (mood tags collected inline via eager Celery)
    # ------------------------------------------------------------------
    def _pass1_save_and_mood(self, candidates):
        saved = []
        for i, (artist, track) in enumerate(candidates, start=1):
            try:
                hits = DeezerService.search_tracks(f"{artist} {track}", limit=1)
            except Exception as e:
                self.stderr.write(f"[seed_graphrag] Deezer search failed for '{artist} - {track}': {e}")
                time.sleep(0.25)
                continue
            if not hits:
                self.stderr.write(f"[seed_graphrag] no Deezer hit for '{artist} - {track}', skipping")
                time.sleep(0.25)
                continue
            try:
                music_id = save_deezer_track_to_db_task(hits[0])
            except Exception as e:
                self.stderr.write(f"[seed_graphrag] save failed for '{artist} - {track}': {e}")
                time.sleep(0.25)
                continue
            if music_id:
                saved.append(music_id)
            time.sleep(0.25)  # Last.fm rate limit courtesy delay
            if i % 10 == 0:
                self.stdout.write(f"[seed_graphrag]   PASS1 progress: {i}/{len(candidates)} processed, {len(saved)} saved")
        return list(Music.objects.filter(music_id__in=saved, is_deleted=False))

    # ------------------------------------------------------------------
    # PASS 2: similar-track edges (real Last.fm, now that all seeds exist)
    # ------------------------------------------------------------------
    def _pass2_similar_edges(self, saved_music):
        for i, m in enumerate(saved_music, start=1):
            artist_name = m.artist.artist_name if m.artist_id else ""
            try:
                fetch_similar_tracks_task(m.music_id, artist_name, m.music_name)
            except Exception as e:
                self.stderr.write(f"[seed_graphrag] similar-track fetch failed for music_id={m.music_id}: {e}")
            time.sleep(0.25)
            if i % 10 == 0:
                self.stdout.write(f"[seed_graphrag]   PASS2 progress: {i}/{len(saved_music)} processed")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def _print_summary(self):
        music_count = Music.objects.count()
        tags_count = Tags.objects.count()
        music_tags_count = MusicTags.objects.count()
        music_similar_count = MusicSimilar.objects.count()
        with_cover = Music.objects.exclude(album__album_image="").filter(album__isnull=False).count()
        with_valence = Music.objects.filter(valence__isnull=False).count()

        self.stdout.write("\n===== seed_graphrag summary =====")
        self.stdout.write(f"music_count={music_count}")
        self.stdout.write(f"tags_count={tags_count}")
        self.stdout.write(f"music_tags_edges={music_tags_count}")
        self.stdout.write(f"music_similar_edges={music_similar_count}")
        self.stdout.write(f"tracks_with_cover={with_cover}")
        self.stdout.write(f"tracks_with_valence={with_valence}")

        self.stdout.write("\n--- sample mood cluster: 'melancholic' ---")
        cluster_tag = Tags.objects.filter(tag_key="melancholic").first()
        if cluster_tag:
            edges = MusicTags.objects.filter(tag=cluster_tag).select_related("music")[:8]
            for e in edges:
                m = e.music
                self.stdout.write(
                    f"  {m.music_name} (music_id={m.music_id}) "
                    f"valence={m.valence} arousal={m.arousal} score={e.score}"
                )
            if not edges:
                self.stdout.write("  (no tracks tagged 'melancholic')")
        else:
            self.stdout.write("  (tag 'melancholic' not present)")

        self.stdout.write("\n--- sample similar edges ---")
        for s in MusicSimilar.objects.select_related("music", "similar_music")[:8]:
            self.stdout.write(
                f"  {s.music.music_name} -> {s.similar_music.music_name} (match={s.match})"
            )
        self.stdout.write("==================================\n")
