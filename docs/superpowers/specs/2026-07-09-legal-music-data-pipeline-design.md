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
- **Last.fm API** (공식, 무료): 무드/분위기 태그(happy·upbeat·positive 등) 수집
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
- 태그가 없으면(커버리지 없음) 곡은 태그 없이 저장. artist.getTopTags fallback은 두지 않음
  (곡 단위 무드가 목적이므로 아티스트 태그로 뭉뚱그리지 않는다).
- **`valence`/`arousal` 수치 필드는 폐기** — 원래 Spotify audio-features 기반이었으나 2024년
  폐기되어 채울 수 없고, Last.fm 텍스트 태그가 그 추천 의도를 대체. 컬럼 drop.

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
| `valence`/`arousal` | 모델 필드·시리얼라이저·OpenSearch 인덱싱 참조 제거, 두 컬럼 drop |
| `music/utils/s3_upload.py` 이미지 업로드 | 삭제 (타 사용처 확인 후) |
| `music/signals.py` 이미지 시그널 | Spotify 태스크 호출로 교체 |
| 문서(`README`, `docs/TREE.md` 등) | 새 아키텍처 반영 |

## 6. 스키마 · 신규 코드

### 스키마 변경 (`managed=False` → raw SQL 마이그레이션 스크립트)
- `music`: `spotify_id`(unique), `isrc` 컬럼 추가; `lyrics`, `valence`, `arousal` 컬럼 drop
- `artists`: `spotify_id` 컬럼 추가
- `albums`: `spotify_id` 컬럼 추가

### 무드 태그 테이블 (신규, 가중치 있는 M:N)
- `tags`: `tag_id`(PK), `tag_name`(unique), `tag_type`(초기값 `'mood'`; 향후 `'genre'` 확장 여지)
- `music_tags`: `music_id`(FK), `tag_id`(FK), `score`(DECIMAL 0~1) — 곡↔태그 연결 강도.
  PK는 `(music_id, tag_id)` 복합. `score`는 Last.fm 태그 `count`(0~100)를 0~1로 정규화한 값.
- 용도: 태그 기반 검색·필터, 그리고 **GraphRAG 추천의 곡–태그 가중 간선**
  (`docs/canvas-graphrag-design.md`)의 입력. 이 관계표를 따라 추천 점수를 전파.
- 기존 `Genres` 모델과 `Music.genre` 문자열 필드는 이번 범위에서 건드리지 않음(장르 태그는 후속).

### 신규 서비스: `music/services/external/spotify.py`
- Client Credentials 토큰 발급·캐싱(만료 1시간 전 갱신)
- `search_tracks(term, market='KR', limit)`, `get_artist(id)`, `get_track(id)`
- 외부 SDK 없이 `requests`로 공식 REST 직접 구현 (의존성 최소화 + "공식 API 직접 연동" 서사)

### 신규 서비스: `music/services/external/lastfm.py`
- `get_track_top_tags(artist, track)` — Last.fm `track.getTopTags` 호출, `(tag_name, count)` 리스트 반환
- 무드 화이트리스트 상수 보유, 화이트리스트 교집합만 필터링해 반환
- `requests` 직접 구현

### 신규 태스크: `fetch_mood_tags_task(music_id, artist_name, track_name)`
- 곡 저장 시그널에서 트리거. Last.fm 조회 → 화이트리스트 필터 → `count` 0~1 정규화 →
  `tags` upsert + `music_tags`(score) 저장.

### 환경변수
- `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` (Spotify Developer Dashboard 무료 발급)
- `LASTFM_API_KEY` (Last.fm API 무료 발급)
- `.env.example`에 추가

### 손대지 않는 범위
- OpenSearch 내부 검색, 차트(자체 재생로그 집계 기반), AI 음악 생성(Suno)은 이번 범위 제외.

## 7. 검증

- 단위 테스트: Spotify 서비스(토큰 갱신·검색 파싱), ISRC 매칭 fallback(iTunes 미매칭 케이스),
  Last.fm 태그 필터링(화이트리스트 교집합·score 정규화·태그 없음 케이스)
- 통합 테스트: 검색 → 상세 → DB 저장 → 아티스트 이미지·무드 태그 태스크 E2E (외부 API mock)
- 최종 확인: 코드베이스 전체에서 `ytmusic|deezer|wikidata|lrclib|lyrics|valence|arousal`
  grep 결과 0건 (`valence`/`arousal`은 이름이 흔하지 않아 잔존 참조 탐지에 유효)
