# 합법적 음악 데이터 파이프라인 + GraphRAG 수집 강화 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 비공식 API(ytmusicapi 등) 의존을 제거하고 Spotify(메타데이터·커버·아티스트 이미지·장르) + iTunes(30초 미리듣기) + Last.fm(무드 태그·유사곡) 공식 API로 음악 데이터를 수집·저장하며, 그 과정에서 GraphRAG 랭킹에 필요한 무드 좌표·곡–곡 유사 엣지·발매일을 함께 적재한다.

**Architecture:** Django 서비스 레이어(`music/services/external/*`)가 공식 REST API를 `requests`로 직접 감싸고, Celery 태스크가 저장·이미지·태그·유사곡을 비동기 처리한다. 저장은 기존 `transaction.atomic()` + `get_or_create`(Artist→Album→Music) 패턴을 계승하되 중복 판정 키를 `spotify_id`로 교체한다. Spotify↔iTunes는 ISRC로 매칭한다.

**Tech Stack:** Python 3, Django 4.2, Django REST Framework, Celery, PostgreSQL 18, `requests`, pytest-django + `responses`(HTTP mock).

## Global Constraints

- 외부 API 호출은 모두 공식·문서화된 엔드포인트만 사용: Spotify Web API, iTunes Search/Lookup API, Last.fm API. 비공식 라이브러리 금지.
- 이미지 파일을 다운로드/재호스팅하지 않는다. DB에는 **URL 문자열만** 저장하고 프론트에서 핫링크한다.
- 도메인 테이블(`music`, `artists`, `albums`, `genres`, `tags`, `music_tags`)은 `managed=True` → 스키마 변경은 Django 마이그레이션으로 처리.
- 저장 시 NOT NULL 컬럼(`music.music_name`, `artists.artist_name`)은 항상 채운다. `created_at`/`updated_at`/`is_deleted`는 TrackableMixin이 자동 설정하므로 직접 세팅하지 않는다.
- 부분 데이터(미리듣기 없음·태그 없음·이미지 없음·유사곡 없음)는 정상 케이스로 취급하고 저장을 실패시키지 않는다.
- 비밀키는 환경변수로만: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `LASTFM_API_KEY`. 코드/커밋에 하드코딩 금지.
- 각 태스크는 커밋으로 끝낸다. 커밋 메시지 말미:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- 작업 브랜치는 `develop`가 아닌 별도 feature 브랜치에서 진행한다.

**Spec:** `docs/superpowers/specs/2026-07-09-legal-music-data-pipeline-design.md`

---

## 실행 전 준비

- [ ] **Feature 브랜치 생성**

```bash
cd /Users/doo._.hyun/Study/Project/MuniVerse/MiniVerseBackend
git checkout develop
git checkout -b feature/legal-music-pipeline
```

- [ ] **Docker DB가 떠 있는지 확인** (마이그레이션·통합 테스트에서 사용)

```bash
docker ps --filter name=miniversebackend-db-1 --format '{{.Names}} {{.Status}}'
```
Expected: `miniversebackend-db-1 Up ... (healthy)`

---

## Phase 0 — 테스트 하네스 & 스키마

### Task 1: pytest-django + responses 테스트 하네스

**Files:**
- Modify: `requirements.txt`
- Create: `pytest.ini`
- Create: `music/tests/__init__.py`
- Create: `music/tests/test_harness.py`

**Interfaces:**
- Produces: `music/tests/` 패키지, `pytest` 실행 환경. 이후 모든 태스크의 테스트가 여기 놓인다.

- [ ] **Step 1: 테스트 의존성 추가**

`requirements.txt` 끝에 추가:

```text
pytest                              # 테스트 러너
pytest-django                       # Django 통합 (DB 픽스처, settings)
responses                           # requests HTTP 목킹
```

- [ ] **Step 2: 설치**

Run: `pip install pytest pytest-django responses`
Expected: 세 패키지 설치 성공.

- [ ] **Step 3: pytest.ini 작성**

`pytest.ini` (프로젝트 루트):

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = test_*.py
testpaths = music/tests
addopts = -p no:cacheprovider
```

- [ ] **Step 4: 하네스 스모크 테스트 작성**

`music/tests/__init__.py`: 빈 파일.

`music/tests/test_harness.py`:

```python
def test_harness_runs():
    assert 1 + 1 == 2


import responses
import requests


@responses.activate
def test_responses_mock_works():
    responses.add(responses.GET, "https://example.test/x", json={"ok": True}, status=200)
    r = requests.get("https://example.test/x", timeout=3)
    assert r.json() == {"ok": True}
```

- [ ] **Step 5: 실행하여 통과 확인**

Run: `python -m pytest music/tests/test_harness.py -v`
Expected: 2 passed. (DB 접근이 없으므로 마이그레이션 없이 통과)

- [ ] **Step 6: 커밋**

```bash
git add requirements.txt pytest.ini music/tests/__init__.py music/tests/test_harness.py
git commit -m "test: pytest-django + responses 테스트 하네스 추가

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 스키마 마이그레이션

기존 실측 스키마(핵심): `music_tags`의 PK가 `(music_id)` 단일이라 한 곡에 태그 하나만 붙는다(M:N 불가). `Tags`는 `tag_key`(unique) 사용, `tag_type` 없음. `MusicTags`는 `score`(nullable) 이미 존재.

**Files:**
- Modify: `music/models.py` (Music·Artists·Albums·Tags·MusicTags 필드, MusicSimilar·ArtistGenres 신규)
- Create: `music/migrations/00XX_legal_pipeline_schema.py` (Django가 생성)

**Interfaces:**
- Produces:
  - `Music.spotify_id: CharField(unique, null)`, `Music.isrc: CharField(null)` (valence/arousal 유지, lyrics 제거)
  - `Artists.spotify_id: CharField(unique, null)`
  - `Albums.spotify_id: CharField(unique, null)`, `Albums.release_date: DateField(null)`
  - `Tags.tag_type: CharField(default='mood')`
  - `MusicTags` PK가 복합 `(music, tag)`로 교체됨
  - `MusicSimilar(music_id, similar_music_id, match)`, `ArtistGenres(artist_id, genre_id)` 모델

- [ ] **Step 1: 모델 필드 수정 — Music**

`music/models.py`의 `class Music` 본문에서 `lyrics` 줄을 제거하고 `spotify_id`, `isrc`를 추가한다. `valence`/`arousal`은 그대로 둔다.

제거:
```python
    lyrics = models.TextField(blank=True, null=True)
```
추가 (`itunes_id` 줄 아래):
```python
    spotify_id = models.CharField(max_length=64, unique=True, blank=True, null=True)
    isrc = models.CharField(max_length=32, blank=True, null=True)
```

- [ ] **Step 2: 모델 필드 수정 — Artists / Albums / Tags**

`class Artists` 본문에 추가:
```python
    spotify_id = models.CharField(max_length=64, unique=True, blank=True, null=True)
```
`class Albums` 본문에 추가:
```python
    spotify_id = models.CharField(max_length=64, unique=True, blank=True, null=True)
    release_date = models.DateField(blank=True, null=True)
```
`class Tags` 본문에 추가 (`tag_key` 줄 아래):
```python
    tag_type = models.CharField(max_length=16, default='mood')
```

- [ ] **Step 3: MusicTags PK 교체**

`class MusicTags`에서 `music` 필드의 `primary_key=True`를 제거하고, Django 복합 PK 대체 수단인 `UniqueConstraint`는 이미 `unique_together`로 있으므로, 대신 `id` 자동 PK가 생기지 않도록 명시적 PK를 둔다. Django는 복합 PK를 지원하지 않으므로 **surrogate PK**를 추가한다.

`class MusicTags`를 다음으로 교체:
```python
class MusicTags(TrackableMixin, models.Model):
    music_tag_id = models.BigAutoField(primary_key=True)
    tag = models.ForeignKey('Tags', models.DO_NOTHING)
    music = models.ForeignKey(Music, models.DO_NOTHING)
    score = models.FloatField(default=0.0, blank=True, null=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        managed = True
        db_table = 'music_tags'
        unique_together = (('music', 'tag'),)
        verbose_name = '음악 태그'
        verbose_name_plural = '2️⃣ 🎵 MUSIC - 음악 태그'
```

- [ ] **Step 4: 신규 모델 — MusicSimilar / ArtistGenres**

`music/models.py` 끝(마지막 클래스 뒤)에 추가:
```python
class MusicSimilar(TrackableMixin, models.Model):
    music_similar_id = models.BigAutoField(primary_key=True)
    music = models.ForeignKey(Music, models.DO_NOTHING, related_name='similar_from')
    similar_music = models.ForeignKey(Music, models.DO_NOTHING, related_name='similar_to')
    match = models.FloatField(default=0.0)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        managed = True
        db_table = 'music_similar'
        unique_together = (('music', 'similar_music'),)
        verbose_name = '유사 곡'
        verbose_name_plural = '2️⃣ 🎵 MUSIC - 유사 곡'


class ArtistGenres(TrackableMixin, models.Model):
    artist_genre_id = models.BigAutoField(primary_key=True)
    artist = models.ForeignKey(Artists, models.DO_NOTHING)
    genre = models.ForeignKey(Genres, models.DO_NOTHING)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        managed = True
        db_table = 'artist_genres'
        unique_together = (('artist', 'genre'),)
        verbose_name = '아티스트 장르'
        verbose_name_plural = '2️⃣ 🎵 MUSIC - 아티스트 장르'
```

- [ ] **Step 5: 마이그레이션 생성**

`music_tags`의 PK 변경은 Postgres에서 기존 PK drop + 신규 컬럼 필요. 로컬 DB에 `music_tags` 데이터가 없으므로(시드 30곡은 태그 없음) 안전.

Run: `python manage.py makemigrations music`
Expected: `music_tags`, `music`, `artists`, `albums`, `tags` 변경 + `MusicSimilar`, `ArtistGenres` 생성 마이그레이션 파일 1개 생성.

- [ ] **Step 6: 마이그레이션 적용**

Run: `python manage.py migrate music`
Expected: 정상 적용. 오류 시(특히 music_tags PK 재정의) 아래로 확인:

Run: `docker exec miniversebackend-db-1 psql -U music_user -d music_db -c "\d music_tags"`
Expected: `music_tag_id`가 PK, `(music_id, tag_id)` UNIQUE 유지.

- [ ] **Step 7: 스키마 검증 테스트**

`music/tests/test_schema.py`:
```python
import pytest
from django.db import connection


@pytest.mark.django_db
def test_music_tags_allows_multiple_tags_per_track():
    from music.models import Music, Tags, MusicTags
    m = Music.objects.create(music_name="T", is_deleted=False)
    t1 = Tags.objects.create(tag_key="happy", tag_type="mood", is_deleted=False)
    t2 = Tags.objects.create(tag_key="upbeat", tag_type="mood", is_deleted=False)
    MusicTags.objects.create(music=m, tag=t1, score=0.9, is_deleted=False)
    MusicTags.objects.create(music=m, tag=t2, score=0.7, is_deleted=False)
    assert MusicTags.objects.filter(music=m).count() == 2


@pytest.mark.django_db
def test_new_columns_exist():
    cols = {c.name for c in connection.introspection.get_table_description(
        connection.cursor(), 'music')}
    assert 'spotify_id' in cols and 'isrc' in cols and 'lyrics' not in cols
```

- [ ] **Step 8: 실행하여 통과 확인**

Run: `python -m pytest music/tests/test_schema.py -v`
Expected: 2 passed. (`--create-db`가 필요하면 `python -m pytest music/tests/test_schema.py -v --create-db`)

- [ ] **Step 9: 커밋**

```bash
git add music/models.py music/migrations/ music/tests/test_schema.py
git commit -m "feat: 합법 파이프라인 스키마 (spotify_id/isrc/release_date, music_tags M:N 수정, music_similar/artist_genres)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 1 — 외부 서비스 (순수 로직, HTTP 목킹)

### Task 3: SpotifyService

**Files:**
- Create: `music/services/external/spotify.py`
- Create: `music/tests/test_spotify_service.py`
- Modify: `config/settings.py` (env 읽기), `.env.example`

**Interfaces:**
- Produces:
  - `SpotifyService.search_tracks(term: str, market='KR', limit=10) -> list[dict]` — 각 dict: `{spotify_id, music_name, artist_name, artist_spotify_id, album_name, album_spotify_id, album_image_640, album_image_300, album_image_64, isrc, release_date, duration, spotify_url}`
  - `SpotifyService.get_artist(artist_spotify_id: str) -> dict` — `{artist_image, genres: list[str], spotify_url}`
  - `SpotifyService.get_track(spotify_id: str) -> dict | None` — search_tracks 항목과 동일 형태
  - 토큰은 클래스 캐시(`_token`, `_token_expires_at`), 만료 60초 전 갱신.

- [ ] **Step 1: 실패 테스트 작성 (토큰 발급 + 검색 파싱)**

`music/tests/test_spotify_service.py`:
```python
import responses
from music.services.external.spotify import SpotifyService


def _mock_token():
    responses.add(
        responses.POST, "https://accounts.spotify.com/api/token",
        json={"access_token": "tok", "token_type": "Bearer", "expires_in": 3600},
        status=200,
    )


SEARCH_BODY = {
    "tracks": {"items": [{
        "id": "sp_track_1",
        "name": "Super Shy",
        "duration_ms": 154000,
        "external_ids": {"isrc": "KRA402400123"},
        "external_urls": {"spotify": "https://open.spotify.com/track/sp_track_1"},
        "artists": [{"id": "sp_artist_1", "name": "NewJeans"}],
        "album": {
            "id": "sp_album_1", "name": "Get Up", "release_date": "2023-07-21",
            "images": [
                {"height": 640, "width": 640, "url": "https://i.scdn.co/image/640"},
                {"height": 300, "width": 300, "url": "https://i.scdn.co/image/300"},
                {"height": 64, "width": 64, "url": "https://i.scdn.co/image/64"},
            ],
        },
    }]}
}


@responses.activate
def test_search_tracks_parses_first_item():
    SpotifyService._token = None
    _mock_token()
    responses.add(responses.GET, "https://api.spotify.com/v1/search",
                  json=SEARCH_BODY, status=200)
    out = SpotifyService.search_tracks("newjeans super shy", limit=1)
    assert len(out) == 1
    item = out[0]
    assert item["spotify_id"] == "sp_track_1"
    assert item["music_name"] == "Super Shy"
    assert item["artist_name"] == "NewJeans"
    assert item["artist_spotify_id"] == "sp_artist_1"
    assert item["album_image_640"] == "https://i.scdn.co/image/640"
    assert item["isrc"] == "KRA402400123"
    assert item["release_date"] == "2023-07-21"
    assert item["duration"] == 154
    assert item["spotify_url"] == "https://open.spotify.com/track/sp_track_1"


@responses.activate
def test_get_artist_returns_image_and_genres():
    SpotifyService._token = None
    _mock_token()
    responses.add(
        responses.GET, "https://api.spotify.com/v1/artists/sp_artist_1",
        json={"id": "sp_artist_1", "genres": ["k-pop", "dance pop"],
              "images": [{"height": 640, "url": "https://i.scdn.co/artist/640"}],
              "external_urls": {"spotify": "https://open.spotify.com/artist/sp_artist_1"}},
        status=200,
    )
    out = SpotifyService.get_artist("sp_artist_1")
    assert out["artist_image"] == "https://i.scdn.co/artist/640"
    assert out["genres"] == ["k-pop", "dance pop"]
```

- [ ] **Step 2: 실행하여 실패 확인**

Run: `python -m pytest music/tests/test_spotify_service.py -v`
Expected: FAIL — `ModuleNotFoundError: music.services.external.spotify`.

- [ ] **Step 3: SpotifyService 구현**

`music/services/external/spotify.py`:
```python
"""
Spotify Web API 통합 서비스 (Client Credentials).
검색·메타데이터·앨범 커버·아티스트 이미지·장르·ISRC 수집.
"""
import base64
import time
import logging
from typing import Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SpotifyService:
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    API_BASE = "https://api.spotify.com/v1"
    TIMEOUT = 5

    _token: Optional[str] = None
    _token_expires_at: float = 0.0

    @classmethod
    def _get_token(cls) -> Optional[str]:
        if cls._token and time.time() < cls._token_expires_at - 60:
            return cls._token
        client_id = settings.SPOTIFY_CLIENT_ID
        client_secret = settings.SPOTIFY_CLIENT_SECRET
        if not client_id or not client_secret:
            logger.error("[Spotify] CLIENT_ID/SECRET 미설정")
            return None
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        try:
            r = requests.post(
                cls.TOKEN_URL,
                data={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {auth}"},
                timeout=cls.TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            cls._token = data["access_token"]
            cls._token_expires_at = time.time() + data.get("expires_in", 3600)
            return cls._token
        except requests.exceptions.RequestException as e:
            logger.error(f"[Spotify] 토큰 발급 실패: {e}")
            return None

    @classmethod
    def _headers(cls) -> Optional[Dict]:
        token = cls._get_token()
        return {"Authorization": f"Bearer {token}"} if token else None

    @staticmethod
    def _pick_image(images: List[Dict], height: int) -> str:
        for img in images or []:
            if img.get("height") == height:
                return img.get("url", "")
        return (images[0].get("url", "") if images else "")

    @classmethod
    def _parse_track(cls, t: Dict) -> Dict:
        album = t.get("album", {}) or {}
        images = album.get("images", []) or []
        artists = t.get("artists", []) or [{}]
        first_artist = artists[0] if artists else {}
        duration_ms = t.get("duration_ms")
        return {
            "spotify_id": t.get("id", ""),
            "music_name": t.get("name", ""),
            "artist_name": first_artist.get("name", ""),
            "artist_spotify_id": first_artist.get("id", ""),
            "album_name": album.get("name", ""),
            "album_spotify_id": album.get("id", ""),
            "album_image_640": cls._pick_image(images, 640),
            "album_image_300": cls._pick_image(images, 300),
            "album_image_64": cls._pick_image(images, 64),
            "isrc": (t.get("external_ids", {}) or {}).get("isrc", ""),
            "release_date": album.get("release_date", ""),
            "duration": int(duration_ms / 1000) if duration_ms else None,
            "spotify_url": (t.get("external_urls", {}) or {}).get("spotify", ""),
        }

    @classmethod
    def search_tracks(cls, term: str, market: str = "KR", limit: int = 10) -> List[Dict]:
        headers = cls._headers()
        if not headers:
            return []
        try:
            r = requests.get(
                f"{cls.API_BASE}/search",
                params={"q": term, "type": "track", "market": market, "limit": limit},
                headers=headers, timeout=cls.TIMEOUT,
            )
            r.raise_for_status()
            items = (r.json().get("tracks", {}) or {}).get("items", []) or []
            return [cls._parse_track(t) for t in items]
        except requests.exceptions.RequestException as e:
            logger.error(f"[Spotify] 검색 실패: {e}")
            return []

    @classmethod
    def get_track(cls, spotify_id: str) -> Optional[Dict]:
        headers = cls._headers()
        if not headers:
            return None
        try:
            r = requests.get(f"{cls.API_BASE}/tracks/{spotify_id}",
                             params={"market": "KR"}, headers=headers, timeout=cls.TIMEOUT)
            r.raise_for_status()
            return cls._parse_track(r.json())
        except requests.exceptions.RequestException as e:
            logger.error(f"[Spotify] 트랙 조회 실패: {e}")
            return None

    @classmethod
    def get_artist(cls, artist_spotify_id: str) -> Dict:
        headers = cls._headers()
        if not headers:
            return {"artist_image": "", "genres": [], "spotify_url": ""}
        try:
            r = requests.get(f"{cls.API_BASE}/artists/{artist_spotify_id}",
                             headers=headers, timeout=cls.TIMEOUT)
            r.raise_for_status()
            data = r.json()
            return {
                "artist_image": cls._pick_image(data.get("images", []), 640),
                "genres": data.get("genres", []) or [],
                "spotify_url": (data.get("external_urls", {}) or {}).get("spotify", ""),
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"[Spotify] 아티스트 조회 실패: {e}")
            return {"artist_image": "", "genres": [], "spotify_url": ""}
```

- [ ] **Step 4: settings + .env.example에 env 추가**

`config/settings.py`의 env 블록(예: OPENSEARCH 설정 근처)에 추가:
```python
# Spotify Web API (Client Credentials)
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID', '')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET', '')
```
`.env.example`에 추가:
```text
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

- [ ] **Step 5: 실행하여 통과 확인**

Run: `python -m pytest music/tests/test_spotify_service.py -v`
Expected: 2 passed.

- [ ] **Step 6: 커밋**

```bash
git add music/services/external/spotify.py music/tests/test_spotify_service.py config/settings.py .env.example
git commit -m "feat: SpotifyService (토큰 캐시, 검색/트랙/아티스트 파싱)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: LastfmService (무드 태그 + 유사곡)

**Files:**
- Create: `music/services/external/lastfm.py`
- Create: `music/tests/test_lastfm_service.py`
- Modify: `config/settings.py`, `.env.example`

**Interfaces:**
- Produces:
  - `LastfmService.MOOD_WHITELIST: set[str]`
  - `LastfmService.get_track_top_tags(artist: str, track: str) -> list[tuple[str, int]]` — 화이트리스트 교집합만, `(tag_key, count)` count 0~100
  - `LastfmService.get_track_similar(artist: str, track: str) -> list[tuple[str, str, float]]` — `(artist_name, track_name, match)` match 0~1

- [ ] **Step 1: 실패 테스트 작성**

`music/tests/test_lastfm_service.py`:
```python
import responses
from music.services.external.lastfm import LastfmService

TAGS_BODY = {"toptags": {"tag": [
    {"name": "happy", "count": 100},
    {"name": "kpop", "count": 90},          # 장르 → 화이트리스트 아님
    {"name": "upbeat", "count": 40},
    {"name": "seen live", "count": 5},       # 잡음
]}}

SIMILAR_BODY = {"similartracks": {"track": [
    {"name": "I AM", "match": "1.0", "artist": {"name": "IVE"}},
    {"name": "Spicy", "match": "0.87", "artist": {"name": "aespa"}},
]}}


@responses.activate
def test_get_track_top_tags_filters_whitelist():
    responses.add(responses.GET, "https://ws.audioscrobbler.com/2.0/",
                  json=TAGS_BODY, status=200)
    out = LastfmService.get_track_top_tags("NewJeans", "Super Shy")
    keys = {k for k, _ in out}
    assert keys == {"happy", "upbeat"}
    assert ("happy", 100) in out


@responses.activate
def test_get_track_similar_parses_match():
    responses.add(responses.GET, "https://ws.audioscrobbler.com/2.0/",
                  json=SIMILAR_BODY, status=200)
    out = LastfmService.get_track_similar("NewJeans", "Super Shy")
    assert ("IVE", "I AM", 1.0) in out
    assert ("aespa", "Spicy", 0.87) in out
```

- [ ] **Step 2: 실행하여 실패 확인**

Run: `python -m pytest music/tests/test_lastfm_service.py -v`
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: LastfmService 구현**

`music/services/external/lastfm.py`:
```python
"""
Last.fm API 통합 서비스. 무드 태그(track.getTopTags)와 곡–곡 유사(track.getSimilar).
"""
import logging
from typing import List, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class LastfmService:
    API_URL = "https://ws.audioscrobbler.com/2.0/"
    TIMEOUT = 5

    MOOD_WHITELIST = {
        "happy", "upbeat", "positive", "uplifting", "feel good", "energetic",
        "chill", "mellow", "melancholic", "sad", "romantic", "dreamy", "dark",
        "calm", "party",
    }

    @classmethod
    def _get(cls, method: str, artist: str, track: str) -> dict:
        api_key = settings.LASTFM_API_KEY
        if not api_key:
            logger.error("[Last.fm] API_KEY 미설정")
            return {}
        try:
            r = requests.get(cls.API_URL, params={
                "method": method, "artist": artist, "track": track,
                "api_key": api_key, "format": "json", "autocorrect": 1,
            }, timeout=cls.TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[Last.fm] {method} 실패: {e}")
            return {}

    @classmethod
    def get_track_top_tags(cls, artist: str, track: str) -> List[Tuple[str, int]]:
        data = cls._get("track.getTopTags", artist, track)
        tags = (data.get("toptags", {}) or {}).get("tag", []) or []
        out = []
        for t in tags:
            key = (t.get("name", "") or "").strip().lower()
            if key in cls.MOOD_WHITELIST:
                try:
                    out.append((key, int(t.get("count", 0))))
                except (TypeError, ValueError):
                    out.append((key, 0))
        return out

    @classmethod
    def get_track_similar(cls, artist: str, track: str) -> List[Tuple[str, str, float]]:
        data = cls._get("track.getSimilar", artist, track)
        tracks = (data.get("similartracks", {}) or {}).get("track", []) or []
        out = []
        for t in tracks:
            name = t.get("name", "") or ""
            a = (t.get("artist", {}) or {}).get("name", "") or ""
            try:
                match = float(t.get("match", 0.0))
            except (TypeError, ValueError):
                match = 0.0
            if name and a:
                out.append((a, name, match))
        return out
```

- [ ] **Step 4: settings + .env.example**

`config/settings.py`:
```python
# Last.fm API
LASTFM_API_KEY = os.getenv('LASTFM_API_KEY', '')
```
`.env.example`:
```text
LASTFM_API_KEY=
```

- [ ] **Step 5: 실행하여 통과 확인**

Run: `python -m pytest music/tests/test_lastfm_service.py -v`
Expected: 2 passed.

- [ ] **Step 6: 커밋**

```bash
git add music/services/external/lastfm.py music/tests/test_lastfm_service.py config/settings.py .env.example
git commit -m "feat: LastfmService (무드 태그 화이트리스트 필터 + 유사곡)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 무드 어휘 사전 (valence/arousal 역산)

**Files:**
- Create: `music/services/internal/mood_lexicon.py`
- Create: `music/tests/test_mood_lexicon.py`

**Interfaces:**
- Produces:
  - `MOOD_COORDS: dict[str, tuple[float, float]]` — tag_key → (valence, arousal)
  - `derive_valence_arousal(scored_tags: list[tuple[str, float]]) -> tuple[float, float] | tuple[None, None]` — `scored_tags`는 `(tag_key, score 0~1)`. score 가중 평균. 매칭 태그 없으면 `(None, None)`.

- [ ] **Step 1: 실패 테스트 작성**

`music/tests/test_mood_lexicon.py`:
```python
from music.services.internal.mood_lexicon import derive_valence_arousal, MOOD_COORDS


def test_single_tag_returns_its_coords():
    v, a = derive_valence_arousal([("happy", 1.0)])
    assert (v, a) == MOOD_COORDS["happy"]


def test_weighted_average_of_two_tags():
    # happy(+0.8,+0.6) score 1.0, sad(-0.7,-0.4) score 1.0 → 평균 (0.05, 0.1)
    v, a = derive_valence_arousal([("happy", 1.0), ("sad", 1.0)])
    assert round(v, 3) == round((0.8 + -0.7) / 2, 3)
    assert round(a, 3) == round((0.6 + -0.4) / 2, 3)


def test_no_known_tags_returns_none():
    assert derive_valence_arousal([("unknown_xyz", 1.0)]) == (None, None)


def test_empty_returns_none():
    assert derive_valence_arousal([]) == (None, None)
```

- [ ] **Step 2: 실행하여 실패 확인**

Run: `python -m pytest music/tests/test_mood_lexicon.py -v`
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 구현**

`music/services/internal/mood_lexicon.py`:
```python
"""
무드 태그 → (valence, arousal) 좌표 사전 및 역산 유틸.
Russell circumplex 근사. valence: 긍정도(-1~+1), arousal: 활기(-1~+1).
"""
from typing import List, Optional, Tuple

MOOD_COORDS = {
    "happy": (0.8, 0.6),
    "upbeat": (0.5, 0.8),
    "positive": (0.7, 0.3),
    "uplifting": (0.7, 0.5),
    "feel good": (0.7, 0.4),
    "energetic": (0.0, 0.9),
    "party": (0.6, 0.8),
    "chill": (0.3, -0.6),
    "mellow": (0.2, -0.5),
    "calm": (0.3, -0.7),
    "dreamy": (0.2, -0.3),
    "romantic": (0.5, -0.2),
    "melancholic": (-0.6, -0.3),
    "sad": (-0.7, -0.4),
    "dark": (-0.6, 0.2),
}


def derive_valence_arousal(
    scored_tags: List[Tuple[str, float]]
) -> Tuple[Optional[float], Optional[float]]:
    total_w = 0.0
    v_sum = 0.0
    a_sum = 0.0
    for key, score in scored_tags:
        coord = MOOD_COORDS.get(key)
        if coord is None:
            continue
        w = max(float(score), 0.0)
        if w == 0.0:
            w = 1.0  # score가 0이어도 태그 존재는 반영
        v_sum += coord[0] * w
        a_sum += coord[1] * w
        total_w += w
    if total_w == 0.0:
        return (None, None)
    return (v_sum / total_w, a_sum / total_w)
```

- [ ] **Step 4: 실행하여 통과 확인**

Run: `python -m pytest music/tests/test_mood_lexicon.py -v`
Expected: 4 passed.

- [ ] **Step 5: 커밋**

```bash
git add music/services/internal/mood_lexicon.py music/tests/test_mood_lexicon.py
git commit -m "feat: 무드 어휘 사전 + valence/arousal 역산

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 2 — 저장 파이프라인 & 태스크

### Task 6: iTunes ISRC 미리듣기 조회 헬퍼

**Files:**
- Modify: `music/services/external/itunes.py` (메서드 추가)
- Create: `music/tests/test_itunes_isrc.py`

**Interfaces:**
- Consumes: 기존 `iTunesService`.
- Produces: `iTunesService.lookup_preview_by_isrc(isrc: str) -> str` — 매칭 곡의 `previewUrl` 또는 `""`.

- [ ] **Step 1: 실패 테스트 작성**

`music/tests/test_itunes_isrc.py`:
```python
import responses
from music.services.external.itunes import iTunesService


@responses.activate
def test_lookup_preview_by_isrc_returns_preview():
    responses.add(
        responses.GET, "https://itunes.apple.com/lookup",
        json={"resultCount": 1, "results": [
            {"wrapperType": "track", "kind": "song",
             "previewUrl": "https://audio.itunes/preview.m4a"}]},
        status=200,
    )
    assert iTunesService.lookup_preview_by_isrc("KRA402400123") == "https://audio.itunes/preview.m4a"


@responses.activate
def test_lookup_preview_by_isrc_no_match_returns_empty():
    responses.add(responses.GET, "https://itunes.apple.com/lookup",
                  json={"resultCount": 0, "results": []}, status=200)
    assert iTunesService.lookup_preview_by_isrc("NOPE") == ""
```

- [ ] **Step 2: 실행하여 실패 확인**

Run: `python -m pytest music/tests/test_itunes_isrc.py -v`
Expected: FAIL — `lookup_preview_by_isrc` 없음.

- [ ] **Step 3: 메서드 추가**

`music/services/external/itunes.py`의 `iTunesService`에 추가:
```python
    @classmethod
    def lookup_preview_by_isrc(cls, isrc: str, country: str = "KR") -> str:
        """ISRC로 iTunes 곡을 찾아 30초 미리듣기 URL을 반환. 없으면 빈 문자열."""
        if not isrc:
            return ""
        try:
            r = requests.get(cls.LOOKUP_ENDPOINT, params={
                "isrc": isrc, "entity": "song", "country": country,
            }, timeout=cls.TIMEOUT)
            r.raise_for_status()
            for result in r.json().get("results", []):
                if result.get("kind") == "song" or result.get("wrapperType") == "track":
                    return result.get("previewUrl", "") or ""
            return ""
        except requests.exceptions.RequestException:
            return ""
```

- [ ] **Step 4: 실행하여 통과 확인**

Run: `python -m pytest music/tests/test_itunes_isrc.py -v`
Expected: 2 passed.

- [ ] **Step 5: 커밋**

```bash
git add music/services/external/itunes.py music/tests/test_itunes_isrc.py
git commit -m "feat: iTunes ISRC 미리듣기 조회 (lookup_preview_by_isrc)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Spotify 저장 태스크

**Files:**
- Create: `music/tasks/spotify_save.py`
- Modify: `music/tasks/__init__.py`
- Create: `music/tests/test_spotify_save_task.py`

**Interfaces:**
- Consumes: `SpotifyService`(dict 형태 §Task3), `iTunesService.lookup_preview_by_isrc`.
- Produces: `save_spotify_track_to_db_task(track: dict) -> int | None` — `track`은 SpotifyService 검색/조회 dict. 저장 후 `music_id`. 중복(spotify_id 기준) 시 기존 id. 저장 성공 시 아티스트 이미지·무드 태그·유사곡 태스크를 `.delay()`로 트리거.

- [ ] **Step 1: 실패 테스트 작성 (중복 방지 + FK 순서 + 부분데이터)**

`music/tests/test_spotify_save_task.py`:
```python
import pytest
from unittest.mock import patch

TRACK = {
    "spotify_id": "sp_track_1", "music_name": "Super Shy",
    "artist_name": "NewJeans", "artist_spotify_id": "sp_artist_1",
    "album_name": "Get Up", "album_spotify_id": "sp_album_1",
    "album_image_640": "https://i.scdn.co/image/640",
    "album_image_300": "https://i.scdn.co/image/300",
    "album_image_64": "https://i.scdn.co/image/64",
    "isrc": "KRA402400123", "release_date": "2023-07-21",
    "duration": 154, "spotify_url": "https://open.spotify.com/track/sp_track_1",
}


@pytest.mark.django_db
@patch("music.tasks.spotify_save.fetch_similar_tracks_task")
@patch("music.tasks.spotify_save.fetch_mood_tags_task")
@patch("music.tasks.spotify_save.fetch_artist_image_task")
@patch("music.tasks.spotify_save.iTunesService.lookup_preview_by_isrc", return_value="https://prev.m4a")
def test_saves_track_with_fk_chain(mock_prev, mock_img, mock_mood, mock_sim):
    from music.tasks.spotify_save import save_spotify_track_to_db_task
    from music.models import Music, Artists, Albums
    mid = save_spotify_track_to_db_task(TRACK)
    m = Music.objects.get(music_id=mid)
    assert m.spotify_id == "sp_track_1"
    assert m.audio_url == "https://prev.m4a"
    assert m.isrc == "KRA402400123"
    assert m.artist.spotify_id == "sp_artist_1"
    assert m.album.spotify_id == "sp_album_1"
    assert str(m.album.release_date) == "2023-07-21"
    assert m.album.album_image == "https://i.scdn.co/image/640"


@pytest.mark.django_db
@patch("music.tasks.spotify_save.fetch_similar_tracks_task")
@patch("music.tasks.spotify_save.fetch_mood_tags_task")
@patch("music.tasks.spotify_save.fetch_artist_image_task")
@patch("music.tasks.spotify_save.iTunesService.lookup_preview_by_isrc", return_value="")
def test_dedup_by_spotify_id(mock_prev, mock_img, mock_mood, mock_sim):
    from music.tasks.spotify_save import save_spotify_track_to_db_task
    from music.models import Music
    first = save_spotify_track_to_db_task(TRACK)
    second = save_spotify_track_to_db_task(TRACK)
    assert first == second
    assert Music.objects.filter(spotify_id="sp_track_1").count() == 1
```

- [ ] **Step 2: 실행하여 실패 확인**

Run: `python -m pytest music/tests/test_spotify_save_task.py -v`
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 저장 태스크 구현**

`music/tasks/spotify_save.py`:
```python
"""
Spotify 트랙을 DB에 저장하는 Celery 태스크.
- 중복 판정: spotify_id
- FK 순서: Artist → Album → Music (transaction.atomic)
- 미리듣기: ISRC로 iTunes 조회
- 저장 성공 시 아티스트 이미지·무드 태그·유사곡 태스크 트리거
"""
import logging
from datetime import datetime
from celery import shared_task
from django.utils import timezone
from django.db import transaction

from ..models import Music, Artists, Albums
from ..services.external.itunes import iTunesService
from .metadata import fetch_artist_image_task
from .enrichment import fetch_mood_tags_task, fetch_similar_tracks_task

logger = logging.getLogger(__name__)


def _parse_date(value: str):
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


@shared_task(bind=True, max_retries=3)
def save_spotify_track_to_db_task(self, track: dict):
    spotify_id = track.get("spotify_id")
    if not spotify_id:
        logger.error("[Spotify 저장] spotify_id 없음")
        return None

    existing = Music.objects.filter(spotify_id=spotify_id, is_deleted=False).first()
    if existing:
        return existing.music_id

    try:
        with transaction.atomic():
            artist = None
            artist_sid = track.get("artist_spotify_id")
            artist_name = track.get("artist_name", "")
            if artist_name:
                artist, a_created = Artists.objects.get_or_create(
                    spotify_id=artist_sid or None,
                    defaults={"artist_name": artist_name, "artist_image": ""},
                )
                if not artist.artist_name:
                    artist.artist_name = artist_name
                    artist.save()

            album = None
            album_sid = track.get("album_spotify_id")
            album_name = track.get("album_name", "")
            if album_sid:
                album, al_created = Albums.objects.get_or_create(
                    spotify_id=album_sid,
                    defaults={
                        "album_name": album_name,
                        "album_image": track.get("album_image_640", ""),
                        "image_large_square": track.get("album_image_640", ""),
                        "image_square": track.get("album_image_300", ""),
                        "release_date": _parse_date(track.get("release_date", "")),
                        "artist": artist,
                    },
                )

            preview = iTunesService.lookup_preview_by_isrc(track.get("isrc", ""))

            music = Music.objects.create(
                spotify_id=spotify_id,
                isrc=track.get("isrc", "") or None,
                music_name=track.get("music_name", ""),
                artist=artist,
                album=album,
                duration=track.get("duration"),
                audio_url=preview,
                is_ai=False,
            )

        # 후속 비동기 수집 (트랜잭션 밖)
        if artist and artist.artist_id:
            fetch_artist_image_task.delay(artist.artist_id, artist.spotify_id, artist_name)
        fetch_mood_tags_task.delay(music.music_id, artist_name, music.music_name)
        fetch_similar_tracks_task.delay(music.music_id, artist_name, music.music_name)
        return music.music_id

    except Exception as e:
        logger.error(f"[Spotify 저장] 실패 spotify_id={spotify_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=10)
        return None
```

- [ ] **Step 4: 태스크 등록**

`music/tasks/__init__.py`에 추가 (import 블록과 `__all__` 양쪽):
```python
from .spotify_save import (
    save_spotify_track_to_db_task,
)
```
`__all__`에 `'save_spotify_track_to_db_task',` 추가.

> 주의: 이 태스크는 Task 8의 `enrichment.py`와 Task 9의 수정된 `metadata.fetch_artist_image_task`(시그니처 `(artist_id, spotify_id, artist_name)`)에 의존한다. Task 8·9가 먼저/함께 있어야 import가 성립하므로, 이 세 태스크는 순서대로 실행하되 Step 5 테스트는 Task 8·9 완료 후 통과한다. 실행 순서를 지키면 각 커밋 시점에 import가 깨지지 않는다. **아래 Step 5 실행 전에 Task 8, Task 9를 먼저 완료할 것.**

- [ ] **Step 5: (Task 8·9 완료 후) 실행하여 통과 확인**

Run: `python -m pytest music/tests/test_spotify_save_task.py -v`
Expected: 2 passed.

- [ ] **Step 6: 커밋**

```bash
git add music/tasks/spotify_save.py music/tasks/__init__.py music/tests/test_spotify_save_task.py
git commit -m "feat: Spotify 저장 태스크 (spotify_id 중복판정, ISRC 미리듣기, 후속 수집 트리거)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: 무드 태그 + 유사곡 수집 태스크

**Files:**
- Create: `music/tasks/enrichment.py`
- Modify: `music/tasks/__init__.py`
- Create: `music/tests/test_enrichment_tasks.py`

**Interfaces:**
- Consumes: `LastfmService`, `derive_valence_arousal`, models `Music/Tags/MusicTags/MusicSimilar`.
- Produces:
  - `fetch_mood_tags_task(music_id, artist_name, track_name)` — Last.fm 태그 → `Tags`/`MusicTags`(score=count/100) + `music.valence/arousal` 갱신.
  - `fetch_similar_tracks_task(music_id, artist_name, track_name)` — Last.fm 유사곡 중 **DB에 이미 있는 곡만** `MusicSimilar` 저장.

- [ ] **Step 1: 실패 테스트 작성**

`music/tests/test_enrichment_tasks.py`:
```python
import pytest
from unittest.mock import patch


@pytest.mark.django_db
@patch("music.tasks.enrichment.LastfmService.get_track_top_tags",
       return_value=[("happy", 100), ("upbeat", 40)])
def test_mood_tags_creates_edges_and_coords(mock_tags):
    from music.tasks.enrichment import fetch_mood_tags_task
    from music.models import Music, MusicTags
    m = Music.objects.create(music_name="Super Shy", is_deleted=False)
    fetch_mood_tags_task(m.music_id, "NewJeans", "Super Shy")
    edges = {mt.tag.tag_key: mt.score for mt in MusicTags.objects.filter(music=m)}
    assert edges == {"happy": 1.0, "upbeat": 0.4}
    m.refresh_from_db()
    assert m.valence is not None and m.arousal is not None


@pytest.mark.django_db
@patch("music.tasks.enrichment.LastfmService.get_track_top_tags", return_value=[])
def test_mood_tags_no_tags_leaves_coords_null(mock_tags):
    from music.tasks.enrichment import fetch_mood_tags_task
    from music.models import Music, MusicTags
    m = Music.objects.create(music_name="X", is_deleted=False)
    fetch_mood_tags_task(m.music_id, "A", "X")
    assert MusicTags.objects.filter(music=m).count() == 0
    m.refresh_from_db()
    assert m.valence is None and m.arousal is None


@pytest.mark.django_db
@patch("music.tasks.enrichment.LastfmService.get_track_similar",
       return_value=[("IVE", "I AM", 1.0), ("aespa", "Spicy", 0.87)])
def test_similar_only_links_existing_tracks(mock_sim):
    from music.tasks.enrichment import fetch_similar_tracks_task
    from music.models import Music, Artists, MusicSimilar
    ive = Artists.objects.create(artist_name="IVE", is_deleted=False)
    src = Music.objects.create(music_name="Super Shy", is_deleted=False)
    # "I AM"은 DB에 존재, "Spicy"는 없음
    Music.objects.create(music_name="I AM", artist=ive, is_deleted=False)
    fetch_similar_tracks_task(src.music_id, "NewJeans", "Super Shy")
    links = MusicSimilar.objects.filter(music=src)
    assert links.count() == 1
    assert links.first().similar_music.music_name == "I AM"
```

- [ ] **Step 2: 실행하여 실패 확인**

Run: `python -m pytest music/tests/test_enrichment_tasks.py -v`
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 구현**

`music/tasks/enrichment.py`:
```python
"""
GraphRAG 강화 수집 태스크: 무드 태그(valence/arousal 역산 포함) + 곡–곡 유사 엣지.
"""
import logging
from celery import shared_task

from ..models import Music, Tags, MusicTags, MusicSimilar
from ..services.external.lastfm import LastfmService
from ..services.internal.mood_lexicon import derive_valence_arousal

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def fetch_mood_tags_task(self, music_id: int, artist_name: str, track_name: str):
    music = Music.objects.filter(music_id=music_id, is_deleted=False).first()
    if not music:
        return None
    try:
        tags = LastfmService.get_track_top_tags(artist_name, track_name)  # [(key,count)]
        scored = []
        for key, count in tags:
            score = max(min(count / 100.0, 1.0), 0.0)
            tag, _ = Tags.objects.get_or_create(
                tag_key=key, defaults={"tag_type": "mood"})
            MusicTags.objects.update_or_create(
                music=music, tag=tag, defaults={"score": score})
            scored.append((key, score))

        valence, arousal = derive_valence_arousal(scored)
        music.valence = valence
        music.arousal = arousal
        music.save(update_fields=["valence", "arousal", "updated_at"])
        return music_id
    except Exception as e:
        logger.error(f"[무드 태그] 실패 music_id={music_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)
        return None


@shared_task(bind=True, max_retries=2)
def fetch_similar_tracks_task(self, music_id: int, artist_name: str, track_name: str):
    music = Music.objects.filter(music_id=music_id, is_deleted=False).first()
    if not music:
        return None
    try:
        similar = LastfmService.get_track_similar(artist_name, track_name)
        linked = 0
        for a_name, t_name, match in similar:
            target = Music.objects.filter(
                music_name__iexact=t_name,
                artist__artist_name__iexact=a_name,
                is_deleted=False,
            ).first()
            if target and target.music_id != music.music_id:
                MusicSimilar.objects.update_or_create(
                    music=music, similar_music=target, defaults={"match": match})
                linked += 1
        return linked
    except Exception as e:
        logger.error(f"[유사곡] 실패 music_id={music_id}: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)
        return None
```

- [ ] **Step 4: 태스크 등록**

`music/tasks/__init__.py`에 추가:
```python
from .enrichment import (
    fetch_mood_tags_task,
    fetch_similar_tracks_task,
)
```
`__all__`에 두 이름 추가.

- [ ] **Step 5: 실행하여 통과 확인**

Run: `python -m pytest music/tests/test_enrichment_tasks.py -v`
Expected: 3 passed.

- [ ] **Step 6: 커밋**

```bash
git add music/tasks/enrichment.py music/tasks/__init__.py music/tests/test_enrichment_tasks.py
git commit -m "feat: 무드 태그(valence/arousal 역산) + 곡-곡 유사 엣지 수집 태스크

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: 아티스트 이미지 태스크 재작성 (Spotify 이미지 + 장르 노드)

**Files:**
- Rewrite: `music/tasks/metadata.py` (fetch_artist_image_task만 남기고 Spotify 기반으로 교체; fetch_album_image_task·fetch_lyrics_task 제거)
- Modify: `music/tasks/__init__.py`
- Create: `music/tests/test_artist_image_task.py`

**Interfaces:**
- Consumes: `SpotifyService.get_artist`, models `Artists/Genres/ArtistGenres`.
- Produces: `fetch_artist_image_task(artist_id: int, artist_spotify_id: str, artist_name: str)` — Spotify에서 이미지 URL·genres 획득 → `artists.artist_image`(+원형/사각 필드 640px) 저장 + `Genres` upsert + `ArtistGenres` 링크.

- [ ] **Step 1: 실패 테스트 작성**

`music/tests/test_artist_image_task.py`:
```python
import pytest
from unittest.mock import patch


@pytest.mark.django_db
@patch("music.tasks.metadata.SpotifyService.get_artist",
       return_value={"artist_image": "https://i.scdn.co/artist/640",
                     "genres": ["k-pop", "dance pop"], "spotify_url": ""})
def test_artist_image_and_genre_nodes(mock_get):
    from music.tasks.metadata import fetch_artist_image_task
    from music.models import Artists, Genres, ArtistGenres
    a = Artists.objects.create(artist_name="NewJeans", spotify_id="sp_artist_1",
                               artist_image="", is_deleted=False)
    fetch_artist_image_task(a.artist_id, "sp_artist_1", "NewJeans")
    a.refresh_from_db()
    assert a.artist_image == "https://i.scdn.co/artist/640"
    assert a.image_large_circle == "https://i.scdn.co/artist/640"
    genre_keys = set(Genres.objects.values_list("genre_name", flat=True))
    assert {"k-pop", "dance pop"}.issubset(genre_keys)
    assert ArtistGenres.objects.filter(artist=a).count() == 2
```

- [ ] **Step 2: 실행하여 실패 확인**

Run: `python -m pytest music/tests/test_artist_image_task.py -v`
Expected: FAIL (기존 metadata.py는 YTMusic 기반이고 시그니처가 다름).

- [ ] **Step 3: metadata.py 재작성**

`music/tasks/metadata.py` 전체를 다음으로 교체:
```python
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
```

- [ ] **Step 4: __init__.py에서 제거된 태스크 정리**

`music/tasks/__init__.py`에서 `fetch_album_image_task`, `fetch_lyrics_task` import와 `__all__` 항목을 제거한다. `fetch_artist_image_task`는 유지.

- [ ] **Step 5: 실행하여 통과 확인**

Run: `python -m pytest music/tests/test_artist_image_task.py -v`
Expected: 1 passed.

- [ ] **Step 6: 커밋**

```bash
git add music/tasks/metadata.py music/tasks/__init__.py music/tests/test_artist_image_task.py
git commit -m "refactor: 아티스트 이미지 태스크 Spotify 기반 재작성 + 장르 노드, 앨범이미지/가사 태스크 제거

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

> 이제 **Task 7 Step 5**(save 태스크 테스트)를 실행해 통과시킨다: `python -m pytest music/tests/test_spotify_save_task.py -v` → 2 passed. Task 7 커밋이 아직이면 이 시점에 완료.

---

## Phase 3 — 뷰 / 시리얼라이저 전환

### Task 10: 검색 뷰 Spotify 전환

**Files:**
- Rewrite: `music/views/search.py`의 `get` 흐름(iTunes → Spotify). 파일 내 다른 뷰(OpenSearch 등)는 유지.
- Modify: `music/serializers/search.py` (필드 정렬)
- Create: `music/tests/test_search_view.py`

**Interfaces:**
- Consumes: `SpotifyService.search_tracks`.
- Produces: `GET /api/v1/search?q=...` 응답 항목에 `spotify_id, music_name, artist_name, album_name, album_image(640), audio_url(없으면 빈값), spotify_url, isrc` 포함. DB 존재 여부(`in_db`) 플래그.

- [ ] **Step 1: 실패 테스트 작성**

`music/tests/test_search_view.py`:
```python
import pytest
from unittest.mock import patch
from rest_framework.test import APIClient

SP_RESULTS = [{
    "spotify_id": "sp1", "music_name": "Super Shy", "artist_name": "NewJeans",
    "artist_spotify_id": "spa1", "album_name": "Get Up", "album_spotify_id": "spal1",
    "album_image_640": "https://i.scdn.co/640", "album_image_300": "",
    "album_image_64": "", "isrc": "KR1", "release_date": "2023-07-21",
    "duration": 154, "spotify_url": "https://open.spotify.com/track/sp1",
}]


@pytest.mark.django_db
@patch("music.views.search.SpotifyService.search_tracks", return_value=SP_RESULTS)
def test_search_returns_spotify_shape(mock_search):
    client = APIClient()
    resp = client.get("/api/v1/search", {"q": "super shy"})
    assert resp.status_code == 200
    item = resp.json()["results"][0]
    assert item["spotify_id"] == "sp1"
    assert item["album_image"] == "https://i.scdn.co/640"
    assert item["spotify_url"] == "https://open.spotify.com/track/sp1"
```

> 참고: 검색 엔드포인트 경로/응답 래핑(`results` 키 등)은 기존 `music/urls.py`와 `SearchView`의 실제 계약에 맞춘다. 위 경로/키가 다르면 실제 값으로 바꾼 뒤 테스트를 고정한다.

- [ ] **Step 2: 실행하여 실패 확인**

Run: `python -m pytest music/tests/test_search_view.py -v`
Expected: FAIL (아직 iTunes 흐름).

- [ ] **Step 3: 검색 뷰 `get` 재작성**

`music/views/search.py` 상단 import에서 `from ..services import iTunesService`를 `from ..services.external.spotify import SpotifyService`로 교체. `get` 본문의 iTunes 호출·아티스트/앨범 인라인 생성 블록을 다음으로 대체:
```python
    def get(self, request):
        query = request.query_params.get('q', '')
        if not query:
            return Response({'error': 'q 파라미터가 필요합니다.'},
                            status=status.HTTP_400_BAD_REQUEST)

        parsed = self.parse_search_query(query)
        term = parsed['term']
        results = []
        if term:
            tracks = SpotifyService.search_tracks(term, limit=10)
            existing = set(
                Music.objects.filter(
                    spotify_id__in=[t['spotify_id'] for t in tracks if t.get('spotify_id')]
                ).values_list('spotify_id', flat=True)
            )
            for t in tracks:
                results.append({
                    'spotify_id': t['spotify_id'],
                    'music_name': t['music_name'],
                    'artist_name': t['artist_name'],
                    'album_name': t['album_name'],
                    'album_image': t['album_image_640'],
                    'audio_url': '',  # 상세/재생 시 ISRC로 채움
                    'isrc': t['isrc'],
                    'spotify_url': t['spotify_url'],
                    'in_db': t['spotify_id'] in existing,
                })
        return Response({'results': results}, status=status.HTTP_200_OK)
```
(태그 검색 파라미터 처리·`parse_search_query`는 유지. iTunes 관련 지역 변수·태스크 호출은 삭제.)

- [ ] **Step 4: 실행하여 통과 확인**

Run: `python -m pytest music/tests/test_search_view.py -v`
Expected: 1 passed.

- [ ] **Step 5: 수동 스모크 (선택, 실 키 필요)**

`.env`에 실제 `SPOTIFY_CLIENT_ID/SECRET` 넣고:
Run: `curl "http://localhost:8000/api/v1/search?q=newjeans"`
Expected: Spotify 형태 결과 JSON.

- [ ] **Step 6: 커밋**

```bash
git add music/views/search.py music/serializers/search.py music/tests/test_search_view.py
git commit -m "refactor: 검색 뷰 Spotify 전환 (커버 640px, spotify_url, ISRC)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: 상세/재생 뷰 spotify_id 전환

**Files:**
- Modify: `music/views/music.py` (상세 조회: itunes_id lookup → spotify_id 기준 + 없으면 SpotifyService.get_track → save 태스크)
- Modify: `music/serializers/music.py` (lyrics/valence/arousal 노출 정리, spotify_url 추가)
- Create: `music/tests/test_detail_view.py`

**Interfaces:**
- Consumes: `SpotifyService.get_track`, `save_spotify_track_to_db_task`.
- Produces: 상세 응답에 `spotify_id, audio_url, spotify_url, valence, arousal` 포함(가사 필드 제거).

- [ ] **Step 1: 실패 테스트 작성**

`music/tests/test_detail_view.py`:
```python
import pytest
from rest_framework.test import APIClient
from music.models import Music


@pytest.mark.django_db
def test_detail_returns_no_lyrics_field():
    m = Music.objects.create(music_name="Super Shy", spotify_id="sp1",
                             audio_url="https://prev.m4a", is_deleted=False)
    client = APIClient()
    resp = client.get(f"/api/v1/music/{m.music_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "lyrics" not in body
    assert body["audio_url"] == "https://prev.m4a"
```

> 실제 상세 엔드포인트 경로/응답 키는 `music/urls.py`에 맞춰 고정한다.

- [ ] **Step 2: 실행하여 실패 확인**

Run: `python -m pytest music/tests/test_detail_view.py -v`
Expected: FAIL (`lyrics` 여전히 노출).

- [ ] **Step 3: 시리얼라이저·뷰 수정**

`music/serializers/music.py`의 `fields`에서 `'lyrics'` 제거, `'spotify_url'`은 계산 필드 또는 `music.album`/저장된 값에서 파생. `music/views/music.py`의 상세 조회에서 `iTunesService.lookup(itunes_id)` 분기를 `Music.objects.filter(spotify_id=...)` 우선 조회로 바꾸고, DB에 없으면 `SpotifyService.get_track(spotify_id)` → `save_spotify_track_to_db_task.delay(track)` 후 202 또는 파싱 결과 즉시 반환.

- [ ] **Step 4: 실행하여 통과 확인**

Run: `python -m pytest music/tests/test_detail_view.py -v`
Expected: 1 passed.

- [ ] **Step 5: 커밋**

```bash
git add music/views/music.py music/serializers/music.py music/tests/test_detail_view.py
git commit -m "refactor: 상세/재생 뷰 spotify_id 전환, 가사 필드 제거

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Phase 4 — 비공식 API 제거 & 마무리

### Task 12: 비공식 서비스·가사·S3 이미지 업로드 제거

**Files:**
- Delete: `music/services/ytmusic.py`, `music/services/deezer.py`, `music/services/wikidata.py`, `music/services/lrclib.py`, `music/services/lyrics_ovh.py`
- Delete: `music/services/external/deezer.py`, `music/services/external/wikidata.py`, `music/services/external/lrclib.py`, `music/services/external/lyrics_ovh.py`
- Modify: `music/services/__init__.py`, `music/services/external/__init__.py`
- Modify: `music/utils/s3_upload.py` (이미지 업로드 함수 제거 or 파일 삭제 — 타 사용처 확인 후)
- Modify: `requirements.txt` (`ytmusicapi` 제거)
- Modify: `music/views/music.py` (WikidataService 등 잔존 import 제거)

**Interfaces:**
- Produces: 코드베이스에서 비공식 API 참조 0.

- [ ] **Step 1: 참조 조사**

Run:
```bash
grep -rln "ytmusic\|Deezer\|Wikidata\|LRCLIB\|LyricsOvh\|lyrics_ovh\|lrclib\|deezer\|wikidata" music --include="*.py" | grep -v migrations | grep -v tests
```
Expected: `services/__init__.py`, `services/external/__init__.py`, `views/music.py` 등. 각 파일에서 해당 import·사용을 제거한다.

- [ ] **Step 2: 서비스 파일 삭제 + __init__ 정리**

```bash
git rm music/services/ytmusic.py music/services/deezer.py music/services/wikidata.py music/services/lrclib.py music/services/lyrics_ovh.py
git rm music/services/external/deezer.py music/services/external/wikidata.py music/services/external/lrclib.py music/services/external/lyrics_ovh.py
```
`music/services/__init__.py`와 `music/services/external/__init__.py`에서 삭제된 서비스 export를 제거하고, `SpotifyService`/`LastfmService`를 추가한다. (`iTunesService`, `opensearch_service`, `AiMusicGenerationService`, `UserStatisticsService`는 유지)

- [ ] **Step 3: S3 이미지 업로드 사용처 확인 후 제거**

Run: `grep -rn "upload_image_to_s3\|is_s3_url" music --include="*.py" | grep -v tests`
남은 사용처(예: 시그널)를 제거/정리한 뒤 `music/utils/s3_upload.py`의 이미지 업로드 함수를 삭제한다. (S3를 다른 용도로 쓰면 그 함수만 남긴다.)

- [ ] **Step 4: requirements에서 ytmusicapi 제거**

`requirements.txt`에서 `ytmusicapi ...` 줄 삭제.

- [ ] **Step 5: import 정상성 확인**

Run: `python -c "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); import music.tasks; import music.services; import music.views.music; print('imports ok')"`
Expected: `imports ok` (ImportError 없이).

- [ ] **Step 6: 전체 테스트 통과 확인**

Run: `python -m pytest music/tests -v`
Expected: 지금까지의 모든 테스트 pass.

- [ ] **Step 7: 최종 grep 검증**

Run: `grep -rn "ytmusic\|deezer\|wikidata\|lrclib\|lyrics_ovh" music --include="*.py" | grep -v migrations`
Expected: 결과 0건.

- [ ] **Step 8: 커밋**

```bash
git add -A
git commit -m "refactor: 비공식 API(ytmusic/deezer/wikidata/lrclib/lyrics_ovh)·가사·S3 이미지 업로드 제거

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 13: 시그널 정리 & 30일 refresh 태스크

**Files:**
- Modify: `music/signals.py` (앨범/아티스트 이미지 시그널을 Spotify 흐름에 맞게 정리 또는 제거 — 이미지 수집은 이제 save 태스크가 트리거)
- Create: `music/tasks/refresh.py`
- Modify: `music/tasks/__init__.py`, `config/settings.py` 또는 `config/celery.py`(Celery Beat 스케줄)
- Create: `music/tests/test_refresh_task.py`

**Interfaces:**
- Produces: `refresh_stale_music_task()` — `updated_at`이 30일 이상 지난 곡의 무드 태그·유사곡을 재수집(태스크 재트리거). Celery Beat 30일 주기 등록.

- [ ] **Step 1: 실패 테스트 작성**

`music/tests/test_refresh_task.py`:
```python
import pytest
from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch


@pytest.mark.django_db
@patch("music.tasks.refresh.fetch_similar_tracks_task")
@patch("music.tasks.refresh.fetch_mood_tags_task")
def test_refresh_retriggers_only_stale(mock_mood, mock_sim):
    from music.tasks.refresh import refresh_stale_music_task
    from music.models import Music
    old = Music.objects.create(music_name="Old", is_deleted=False)
    Music.all_objects.filter(pk=old.pk).update(
        updated_at=timezone.now() - timedelta(days=40))
    Music.objects.create(music_name="Fresh", is_deleted=False)  # 최근
    refresh_stale_music_task()
    assert mock_mood.delay.call_count == 1
```

- [ ] **Step 2: 실행하여 실패 확인**

Run: `python -m pytest music/tests/test_refresh_task.py -v`
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: refresh 태스크 구현**

`music/tasks/refresh.py`:
```python
"""
30일 지난 곡 메타데이터(무드 태그·유사곡) 재수집 — Spotify/Last.fm 신선도 조항 대응.
"""
import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

from ..models import Music
from .enrichment import fetch_mood_tags_task, fetch_similar_tracks_task

logger = logging.getLogger(__name__)


@shared_task(name="music.tasks.refresh_stale_music")
def refresh_stale_music_task(days: int = 30):
    cutoff = timezone.now() - timedelta(days=days)
    stale = Music.objects.filter(updated_at__lt=cutoff, is_deleted=False)
    count = 0
    for m in stale.iterator():
        artist_name = m.artist.artist_name if m.artist else ""
        fetch_mood_tags_task.delay(m.music_id, artist_name, m.music_name)
        fetch_similar_tracks_task.delay(m.music_id, artist_name, m.music_name)
        count += 1
    logger.info(f"[refresh] {count}곡 재수집 트리거")
    return count
```

- [ ] **Step 4: 등록 + Beat 스케줄**

`music/tasks/__init__.py`에 `from .refresh import refresh_stale_music_task` 추가(+`__all__`). `config/celery.py`(또는 settings의 `CELERY_BEAT_SCHEDULE`)에 30일 주기 항목 추가:
```python
    "refresh-stale-music": {
        "task": "music.tasks.refresh_stale_music",
        "schedule": 60 * 60 * 24 * 30,  # 30일
    },
```

- [ ] **Step 5: 시그널 정리**

`music/signals.py`의 `album_image_changed`·`artist_image_changed`가 삭제된 `fetch_album_image_task`/구 시그니처 `fetch_artist_image_task`를 참조하면 제거하거나, 아티스트 이미지는 save 태스크가 이미 트리거하므로 해당 시그널 핸들러를 삭제한다. `create_default_playlist` 등 이미지와 무관한 시그널은 유지.

- [ ] **Step 6: 실행하여 통과 확인**

Run: `python -m pytest music/tests/test_refresh_task.py -v`
Expected: 1 passed.

- [ ] **Step 7: import 정상성 + 전체 테스트**

Run: `python -m pytest music/tests -v`
Expected: 전체 pass.

- [ ] **Step 8: 커밋**

```bash
git add music/signals.py music/tasks/refresh.py music/tasks/__init__.py config/celery.py config/settings.py music/tests/test_refresh_task.py
git commit -m "feat: 30일 메타데이터 refresh 태스크 + 이미지 시그널 정리

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 14: OpenSearch 인덱싱 정합 + 프론트엔드 정리

**Files:**
- Modify: `music/management/commands/opensearch_setup.py` (valence/arousal는 유지되므로 그대로; lyrics 참조가 있으면 제거)
- Modify (frontend): 가사 UI 컴포넌트 제거, "Open on Spotify" 링크 + attribution, 커버 이미지 핫링크 처리
- Modify: `MuniVerseFrontend/src/api/music.ts`, 관련 타입

**Interfaces:**
- Produces: 프론트에서 가사 UI 제거, Spotify/Last.fm attribution 노출, 커버는 DB의 Spotify URL 핫링크.

- [ ] **Step 1: 백엔드 잔존 lyrics 참조 제거**

Run: `grep -rn "lyrics" music --include="*.py" | grep -v migrations | grep -v tests`
남은 참조(시리얼라이저·인덱싱·뷰)를 제거한다. valence/arousal는 유지이므로 건드리지 않는다.

- [ ] **Step 2: 프론트 가사/출처 표시 조사**

Run: `grep -rln "lyrics\|가사" /Users/doo._.hyun/Study/Project/MuniVerse/MuniVerseFrontend/src`
해당 컴포넌트에서 가사 표시 블록을 제거하고, 트랙/앨범 카드에 `spotify_url` 링크 버튼과 "Powered by Spotify · Tags by Last.fm" attribution 텍스트를 추가한다. 커버 `<img src>`는 백엔드가 준 Spotify URL을 그대로 사용(핫링크).

- [ ] **Step 3: 프론트 타입 갱신**

`MuniVerseFrontend/src/api/music.ts`의 트랙 타입에서 `lyrics` 제거, `spotify_id`·`spotify_url`·`isrc` 추가.

- [ ] **Step 4: 프론트 빌드 확인**

Run: `cd /Users/doo._.hyun/Study/Project/MuniVerse/MuniVerseFrontend && npm run build`
Expected: 타입/빌드 에러 없음.

- [ ] **Step 5: 커밋 (백엔드·프론트 각 레포)**

백엔드:
```bash
cd /Users/doo._.hyun/Study/Project/MuniVerse/MiniVerseBackend
git add music/ && git commit -m "chore: 잔존 lyrics 참조 제거 (OpenSearch/시리얼라이저)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
프론트:
```bash
cd /Users/doo._.hyun/Study/Project/MuniVerse/MuniVerseFrontend
git add src/ && git commit -m "refactor: 가사 UI 제거, Spotify 링크/attribution, 커버 핫링크, 타입 갱신

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 15: 시드 스크립트 재작성 & 문서 갱신

**Files:**
- Modify: `test_default_playlist.py` 또는 시드 관련 management command (가짜 시드 30곡 → spotify_id 기반 실 데이터 수집 안내로 교체)
- Modify: `README.md`, `docs/TREE.md` 및 관련 문서
- Create: `music/management/commands/graph_readiness.py` (GraphRAG 준비 상태 리포트 — spec/graphrag 문서 §12)

**Interfaces:**
- Produces: `python manage.py graph_readiness` — music/tag/edge 카운트 및 `ready` 플래그 출력.

- [ ] **Step 1: graph_readiness 커맨드 작성**

`music/management/commands/graph_readiness.py`:
```python
from django.core.management.base import BaseCommand
from music.models import Music, Tags, MusicTags, MusicSimilar


class Command(BaseCommand):
    help = "GraphRAG 준비 상태 리포트"

    def handle(self, *args, **opts):
        music_count = Music.objects.count()
        tag_count = Tags.objects.count()
        edge_count = MusicTags.objects.count()
        similar_count = MusicSimilar.objects.count()
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
```

- [ ] **Step 2: 실행 확인**

Run: `python manage.py graph_readiness`
Expected: 카운트와 `ready=...` 출력(초기엔 대부분 0, `ready=false`).

- [ ] **Step 3: 시드 스크립트 정리**

`test_default_playlist.py`의 가짜 아티스트/곡 생성 부분은 `spotify_id`가 없어 새 파이프라인과 맞지 않으므로, 시드가 필요하면 "검색 API를 몇 번 호출해 실제 Spotify 곡을 적재"하는 방식으로 주석/스크립트를 갱신하거나 해당 가짜 시드 로직을 제거한다.

- [ ] **Step 4: 문서 갱신**

`README.md`와 `docs/TREE.md`에서 YouTube Music/Deezer/가사 관련 설명을 제거하고, 새 아키텍처(Spotify+iTunes+Last.fm, ISRC 매칭, 무드 태그/유사 엣지, 약관 준수 장치)를 반영한다. 환경변수 섹션에 `SPOTIFY_CLIENT_ID/SECRET`, `LASTFM_API_KEY` 추가.

- [ ] **Step 5: 커밋**

```bash
git add music/management/commands/graph_readiness.py test_default_playlist.py README.md docs/
git commit -m "docs: graph_readiness 커맨드, 시드/문서 새 파이프라인 반영

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## 최종 검증

- [ ] **전체 백엔드 테스트**

Run: `cd /Users/doo._.hyun/Study/Project/MuniVerse/MiniVerseBackend && python -m pytest music/tests -v`
Expected: 전부 pass.

- [ ] **비공식 API 흔적 0건**

Run: `grep -rn "ytmusic\|deezer\|wikidata\|lrclib\|lyrics_ovh\|lyrics" music --include="*.py" | grep -v migrations | grep -v tests`
Expected: 0건 (valence/arousal는 검색 대상 아님, 유지).

- [ ] **엔드투엔드 스모크 (실 키 필요)**

`.env`에 Spotify/Last.fm 키 설정 후 Celery 워커 실행 → 검색 → 상세 조회 → `graph_readiness`로 무드 태그/유사 엣지가 쌓이는지 확인.

- [ ] **PR 준비**

```bash
git push -u origin feature/legal-music-pipeline
```
`develop` 대상 PR 생성.
