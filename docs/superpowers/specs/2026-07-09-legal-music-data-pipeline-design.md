# MuniVerse 음악 데이터 파이프라인 리팩토링 — 설계 문서

- 작성일: 2026-07-09
- 상태: 승인됨 (구현 대기)
- 범위: `MiniVerseBackend` (주), `MuniVerseFrontend` (부수 변경)

## 1. 배경 및 목표

기존 MuniVerse는 음악 URL·앨범 커버 등을 **비공식 API**(ytmusicapi 등)로 수집했다.
포트폴리오 관점에서 데이터 출처의 합법성에 의문이 생기는 부분이었다.

이번 리팩토링의 목표는 **100% 공식·문서화된 API + 서비스 약관 준수 구조**로 전환하는 것이다.

- **Spotify Web API** (공식, Client Credentials 플로우): 검색, 메타데이터, 앨범 커버(최대 640px),
  아티스트 이미지, ISRC 표준 식별자
- **iTunes Search/Lookup API** (공식): 30초 미리듣기 `previewUrl` 전담
- **Last.fm API** (공식, 무료): 무드 태그(`track.getTopTags`) + 곡–곡 유사(`track.getSimilar`)
- Spotify↔iTunes 카탈로그는 **ISRC**(국제 표준 녹음 코드)로 정확히 매칭

### 합법성 근거 (조사 결과)

- Spotify 텍스트 메타데이터(곡명·아티스트·앨범·ID·재생시간·이미지 URL 문자열)를 앱 운영에
  필요한 범위에서 DB에 캐싱하는 것은 Developer Terms가 허용한다.
- 단, 3가지 준수 조건: ① 무기한 저장 금지(주기적 갱신·삭제) ② 출처 링크백 표시
  ③ 대량 카탈로그 구축 금지(사용자가 실제로 조회/재생한 곡만 캐싱).
- **이미지 파일 자체를 다운로드해 재호스팅하는 것은 위반** → URL 문자열만 저장하고 프론트에서
  Spotify CDN을 핫링크한다. (기존 S3 이미지 업로드 파이프라인 전면 삭제)
- 2024-11-27 이후 신규 등록 Spotify 앱은 `preview_url`을 받을 수 없으므로, 미리듣기 오디오는
  iTunes 공식 API를 사용한다.

## 2. 전제 조건

- 운영 RDS·S3 미연결 상태. 현재는 로컬 Docker Postgres(`miniversebackend-db-1`)만 사용.
- 로컬 DB에는 가짜 시드 데이터(음악 30곡, 아티스트 8명, 이미지·가사 전부 NULL)만 존재.
- 따라서 **데이터 마이그레이션 불필요** — 새 파이프라인으로 처음부터 적재한다.
  기존 시드 스크립트는 새 파이프라인 기준(`spotify_id` 보유)으로 재작성한다.

## 3. 데이터 흐름 (현행 → 변경)

### 검색
- 현행 iTunes 검색 → **Spotify Search API** (`market=KR`)로 교체.
- Spotify 검색 응답 한 번에 커버 URL 3종(640/300/64), 아티스트, ISRC(`external_ids.isrc`),
  Spotify 링크(`external_urls.spotify`)가 모두 포함 → 검색 화면은 API 1회 호출로 완결.

### 상세 조회 / 재생
- 현행 `itunes_id` lookup → **`spotify_id` 기준 조회**로 교체.
- DB에 없으면: ISRC로 iTunes Lookup(`/lookup?isrc=<ISRC>`) 호출 → `previewUrl` 획득 →
  기존 `save_itunes_track_to_db_task`와 동일한 Celery 비동기 저장 패턴 사용.
- iTunes 매칭 실패 시: 미리듣기 없이 저장(프론트는 Spotify 링크만 노출, `audio_url`은 빈 값).

### 아티스트 이미지
- Spotify 검색의 트랙 객체는 simplified artist(이미지 없음)만 포함.
- 저장 시점 시그널 → Celery 태스크가 **Spotify `/artists/{id}` 1회 호출**해 이미지 URL 저장.
- 현행 3단 fallback 체인(YouTube Music → Wikidata → Deezer)은 통째로 삭제.

### 이미지 저장 방식 (핵심 변경)
- S3 다운로드·리사이징 파이프라인 전체 삭제.
- DB에는 **Spotify CDN URL 문자열만** 저장, 프론트에서 핫링크.
- 기존 리사이즈 필드 → Spotify 제공 사이즈로 매핑:
  - `albums.album_image`, `albums.image_large_square` ← 640px URL
  - `albums.image_square` ← 300px URL
  - `artists.artist_image` ← 640px URL
  - 아티스트 원형 필드(`image_large_circle`, `image_small_circle`), 사각형(`image_square`)
    ← 640px URL + 프론트 CSS 크롭(원형/사이즈는 표현 계층에서 처리)

### 무드 태그 (신규)
- 곡 저장 시점 시그널 → Celery 태스크가 **Last.fm `track.getTopTags`**(artist + track 이름 기반)
  호출. 응답의 top tags를 **큐레이션된 무드 화이트리스트**로 필터링해 저장.
- 무드 화이트리스트 예: `happy, upbeat, positive, uplifting, feel good, energetic, chill,
  mellow, melancholic, sad, romantic, dreamy, dark, calm, party` (초기 세트, 확장 가능).
  Last.fm top tags는 장르·잡음("favorites", "seen live" 등)이 섞이므로 화이트리스트 교집합만 채택.
- 태그가 없으면(커버리지 없음) 곡은 태그 없이 저장. artist.getTopTags fallback은 이번 범위에서
  두지 않음(곡 단위 무드가 목적. 아티스트 태그 fallback은 후속).
- **`valence`/`arousal` 수치 필드는 폐기하지 않고, Last.fm 무드 태그에서 역산해 부활**시킨다.
  (Spotify audio-features는 2024년 폐기되어 못 쓰지만, GraphRAG의 mood_score·HAS_MOOD 엣지가
  이 두 값에 의존하므로 유지가 필요.) → 아래 §3.5 참조.

### 3.5 무드 좌표 역산 (valence/arousal 부활)
- 목적: GraphRAG 랭킹의 `mood_score`(0.15)와 `(Track)-[:HAS_MOOD]->(MoodBucket)` 엣지를 살림.
  (`docs/canvas-graphrag-design.md` §7.2, §8)
- **무드 어휘 사전**(코드 상수): 화이트리스트 각 태그에 (valence, arousal) 좌표를 부여.
  예: `happy→(+0.8,+0.6)`, `upbeat→(+0.5,+0.8)`, `positive→(+0.7,+0.3)`, `energetic→(0,+0.9)`,
  `chill→(+0.3,-0.6)`, `mellow→(+0.2,-0.5)`, `sad→(-0.7,-0.4)`, `dark→(-0.6,+0.2)`,
  `romantic→(+0.5,-0.2)`, `dreamy→(+0.2,-0.3)`, `calm→(+0.3,-0.7)`, `party→(+0.6,+0.8)`.
- 곡의 valence/arousal = 그 곡 무드 태그들의 좌표를 **score 가중 평균**한 값 → `music.valence`,
  `music.arousal`에 저장. 무드 태그가 없으면 null(mood_score는 그 곡에 대해 0 기여).
- 추가 외부 API 비용 0(어차피 수집하는 태그를 재사용). 무드 사전은 이후 확장/튜닝 가능.

### 3.6 곡–곡 유사 엣지 (GraphRAG 핵심 구조)
- 곡 저장 시 **Last.fm `track.getSimilar`**(artist + track) 호출 → 유사곡 + `match`(0~1) 획득.
- **우리 DB에 이미 존재하는 곡만** 엣지로 저장(방식 ⓐ). 대량 스텁 저장 안 함
  → Spotify "카탈로그 구축 금지" 준수 + 사용자가 실제 조회한 곡 중심.
- 저장 시점 순서로 아직 없던 유사곡은 30일 refresh 때 점진적으로 연결.
- 효과: 태그를 거치지 않는 곡→곡 순회, 다중 홉 설명 경로, 콜드스타트 곡 편입.

### 3.7 발매일 (freshness)
- Spotify 트랙 응답의 `album.release_date`(또는 iTunes `releaseDate`) 저장 → GraphRAG
  `freshness_score`(0.05)의 데이터 출처 제공. 앨범 레벨로 `albums.release_date`에 저장.

### 3.8 아티스트 장르 노드 (IN_GENRE 클러스터링)
- 아티스트 이미지 조회용 Spotify `/artists/{id}` 응답에 **이미 포함된 `genres` 배열**을 파싱
  (추가 호출 0) → `Genres` 테이블 upsert + `(Artist)-[:IN_GENRE]->(Genre)` 링크(신규
  `artist_genres` 연결 테이블) 저장.
- 효과: 공유 장르 노드를 통한 곡 클러스터링·후보 경로. 단 아티스트 레벨이라 정밀도·커버리지는
  보조 신호 수준(빈 배열 아티스트 다수). 기존 `Music.genre` 단일 문자열은 iTunes 값 유지(병행).

## 4. 약관 준수 장치 (포트폴리오 어필 포인트)

1. **출처 링크백**: 시리얼라이저에 `spotify_url`(트랙/앨범/아티스트) 포함. 프론트에서
   "Open on Spotify" 링크 + attribution 노출 → Developer Policy 링크백 의무 이행.
   Last.fm 태그 표기 화면에는 Last.fm attribution 함께 노출(Last.fm API 이용약관 준수).
2. **데이터 신선도**: Celery Beat에 **30일 주기 메타데이터 refresh 태스크** 추가. 오래된 곡
   재조회, Spotify에서 사라진 곡 soft delete → "무기한 저장 금지" 조항 대응.
3. **캐싱 범위 제한**: 사용자가 검색/재생한 곡만 저장(사전 대량 수집 없음) →
   "카탈로그 구축 금지" 준수.
4. **Last.fm 신선도·범위**: 무드 태그도 30일 refresh 대상에 포함, 곡 단위 조회만 수행.

## 5. 삭제 목록 (비공식 API 흔적 제거)

| 대상 | 조치 |
|---|---|
| `music/services/ytmusic.py` | 파일 삭제 + `requirements.txt`의 `ytmusicapi` 제거 |
| `music/services/{deezer,wikidata,lrclib,lyrics_ovh}.py` | 루트 및 `external/` 중복본 모두 삭제 |
| `music/services/external/{deezer,wikidata,lrclib,lyrics_ovh}.py` | 삭제 |
| `music/services/__init__.py` | 삭제된 서비스 export 제거, Spotify 서비스 추가 |
| `music/tasks/metadata.py` | fallback 체인·S3 업로드 제거, Spotify 기반 아티스트 이미지 태스크로 재작성. `fetch_lyrics_task` 제거, **`fetch_mood_tags_task`(Last.fm) 신규 추가** |
| 가사 기능 | `fetch_lyrics_task`, 관련 시리얼라이저·뷰 필드·프론트 UI 제거, `music.lyrics` 컬럼 drop |
| `music/utils/s3_upload.py` 이미지 업로드 | 삭제 (타 사용처 확인 후) |
| `music/signals.py` 이미지 시그널 | Spotify 태스크 호출로 교체 |
| 문서(`README`, `docs/TREE.md` 등) | 새 아키텍처 반영 |

## 6. 스키마 · 신규 코드

### 스키마 변경 (도메인 테이블은 `managed=True` → 일반 Django 마이그레이션)
- `music`, `artists`, `albums`, `genres`는 `managed=True`이므로 `makemigrations`로 처리
  (auth/django 시스템 테이블만 `managed=False`, 이번 변경과 무관).
- `music`: `spotify_id`(unique), `isrc` 컬럼 추가; `lyrics` 컬럼 drop.
  `valence`/`arousal`은 **유지**(Last.fm 무드 사전에서 역산해 채움, §3.5).
- `artists`: `spotify_id`(unique) 컬럼 추가
- `albums`: `spotify_id`(unique), `release_date`(date, nullable) 컬럼 추가

### GraphRAG 강화 테이블 (신규)
- `music_similar`: `music_id`(FK), `similar_music_id`(FK), `match`(DECIMAL 0~1). PK
  `(music_id, similar_music_id)`. Last.fm `track.getSimilar` 결과 중 **DB에 존재하는 곡만** 저장.
  `(Track)-[:SIMILAR {match}]->(Track)` 엣지. (§3.6)
- `artist_genres`: `artist_id`(FK), `genre_id`(FK, `Genres` 참조). PK `(artist_id, genre_id)`.
  Spotify 아티스트 `genres` 배열 → `Genres` upsert 후 링크. `(Artist)-[:IN_GENRE]->(Genre)`. (§3.8)

### 스키마 안전 매핑 원칙 (API 응답 → 기존 테이블)
- **저장 패턴 유지**: 기존 `save_itunes_track_to_db_task`처럼 `transaction.atomic()` 안에서
  **Artist → Album → Music 순서**로 `get_or_create`. FK 순서·부분 실패 방지 그대로 계승.
- **중복 판정 키 교체**: 현행 Artist 중복 판정은 `artist_name`(동명이인 충돌 위험) →
  **`spotify_id` 기준**으로 교체. Album·Music도 `spotify_id` 기준. 데이터 무결성 개선.
- **NOT NULL 준수**: `music_name`, `artist_name`은 Spotify가 항상 제공 → 안전.
  `album_name`은 nullable(싱글 등 허용). `created_at/updated_at/is_deleted`는
  TrackableMixin이 자동(`auto_now_add`/`auto_now`/`default=False`) → 직접 세팅 금지.
- **URL 길이**: `audio_url` varchar(200), `album_image` varchar(255)에 Spotify 커버(~64자)·
  iTunes preview(~110자) 모두 수용. (신규 태그/이미지 URL도 길이 초과 없음 확인)
- **부분 데이터 허용**: iTunes 미매칭(미리듣기 없음)·Last.fm 태그 없음·아티스트 이미지 미확보는
  모두 정상 케이스로 취급(빈 값 저장). 저장 자체를 실패시키지 않음.

### 무드 태그 테이블 (신규, 가중치 있는 M:N)
- `tags`: `tag_id`(PK), `tag_name`(unique), `tag_type`(초기값 `'mood'`; 향후 `'genre'` 확장 여지)
- `music_tags`: `music_id`(FK), `tag_id`(FK), `score`(DECIMAL 0~1) — 곡↔태그 연결 강도.
  PK는 `(music_id, tag_id)` 복합. `score`는 Last.fm 태그 `count`(0~100)를 0~1로 정규화한 값.
- 용도: 태그 기반 검색·필터, 그리고 **GraphRAG 추천의 곡–태그 가중 간선**
  (`docs/canvas-graphrag-design.md`)의 입력. 이 관계표를 따라 추천 점수를 전파.
- `Genres` 테이블은 §3.8 아티스트 장르 노드로 활용(신규 `artist_genres` 링크). `Music.genre`
  단일 문자열은 iTunes 값으로 병행 유지.

### 신규 서비스: `music/services/external/spotify.py`
- Client Credentials 토큰 발급·캐싱(만료 1시간 전 갱신)
- `search_tracks(term, market='KR', limit)`, `get_artist(id)`, `get_track(id)`
- 외부 SDK 없이 `requests`로 공식 REST 직접 구현 (의존성 최소화 + "공식 API 직접 연동" 서사)

### 신규 서비스: `music/services/external/lastfm.py`
- `get_track_top_tags(artist, track)` — `track.getTopTags` 호출, `(tag_name, count)` 리스트 반환.
  무드 화이트리스트 교집합만 필터링.
- `get_track_similar(artist, track)` — `track.getSimilar` 호출, `(artist, track, match)` 리스트 반환.
- `requests` 직접 구현.

### 신규 모듈: `music/services/internal/mood_lexicon.py`
- 무드 화이트리스트 태그 → (valence, arousal) 좌표 사전(상수). score 가중 평균 유틸 포함. (§3.5)

### 신규 태스크: `fetch_mood_tags_task(music_id, artist_name, track_name)`
- 곡 저장 시그널에서 트리거. Last.fm `getTopTags` → 화이트리스트 필터 → `count` 0~1 정규화 →
  `tags` upsert + `music_tags`(score) 저장 → 무드 사전으로 `valence`/`arousal` 계산·저장(§3.5).

### 신규 태스크: `fetch_similar_tracks_task(music_id, artist_name, track_name)`
- 곡 저장 시그널에서 트리거. Last.fm `getSimilar` → **DB에 이미 있는 곡만** `music_similar` 저장. (§3.6)

### 아티스트 이미지 태스크 (재작성)
- Spotify `/artists/{id}` 응답에서 이미지 URL + **`genres` 배열** 파싱 → 이미지 저장 +
  `Genres` upsert + `artist_genres` 링크. (§3.8) 추가 호출 없음.

### 환경변수
- `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` (Spotify Developer Dashboard 무료 발급)
- `LASTFM_API_KEY` (Last.fm API 무료 발급)
- `.env.example`에 추가

### 손대지 않는 범위
- OpenSearch 내부 검색, 차트(자체 재생로그 집계 기반), AI 음악 생성(Suno)은 이번 범위 제외.

## 7. 검증

- 단위 테스트: Spotify 서비스(토큰 갱신·검색 파싱), ISRC 매칭 fallback(iTunes 미매칭 케이스),
  Last.fm 태그 필터링(화이트리스트 교집합·score 정규화·태그 없음 케이스),
  무드 사전 역산(score 가중 평균·태그 없음 시 null), 유사 엣지(DB 미존재 곡 제외)
- 통합 테스트: 검색 → 상세 → DB 저장 → 아티스트 이미지·무드 태그·유사곡 태스크 E2E (외부 API mock)
- 최종 확인: 코드베이스 전체에서 `ytmusic|deezer|wikidata|lrclib|lyrics` grep 결과 0건
  (`valence`/`arousal`은 유지되므로 검색어에서 제외)
