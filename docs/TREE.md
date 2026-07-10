# 📁 프로젝트 파일 구조

> 마지막 업데이트: 2026-07-10 (비공식 API 제거, Spotify+iTunes+Last.fm 공식 음악 데이터 파이프라인 반영)
```
Backend/
├── 📄 manage.py              # Django 관리 명령어 진입점
│
├── 📂 config/                # Django 프로젝트 설정 폴더
│   ├── __init__.py          # config 패키지 초기화
│   ├── settings.py          # Django 설정 (DB, Celery Beat 스케줄 등)
│   ├── urls.py              # URL 라우팅 설정
│   ├── wsgi.py              # WSGI 애플리케이션 (배포용)
│   ├── asgi.py              # ASGI 애플리케이션 (비동기 지원)
│   └── celery.py            # Celery 비동기 작업 설정
│
├── 📂 music/                 # music 앱 (음악 도메인)
│   ├── __init__.py
│   ├── admin.py             # Django Admin 등록
│   ├── apps.py              # 앱 설정
│   ├── models.py            # 데이터 모델 (Music, Charts, PlayLogs 등)
│   ├── urls.py              # URL 라우팅
│   ├── tasks.py             # Celery 작업 (차트 계산, 데이터 정리)
│   ├── tests.py             # 테스트
│   │
│   ├── 📂 serializers/      # Serializers 모듈 (JSON 직렬화)
│   │   ├── __init__.py      # 모든 Serializer export
│   │   ├── base.py          # 기본 (Artist, Album, Tag, AiInfo)
│   │   ├── music.py         # 음악 관련 (MusicDetail, MusicLike)
│   │   ├── search.py        # 검색 관련 (iTunesSearchResult)
│   │   ├── auth.py          # 인증 관련 (UserRegister, UserLogin)
│   │   └── charts.py        # 차트 관련 (PlayLog, ChartItem, ChartResponse)
│   │
│   ├── 📂 views/            # Views 모듈 (API 엔드포인트)
│   │   ├── __init__.py      # 모든 View export
│   │   ├── common.py        # 공통 유틸 (MusicPagination, ErrorTestView, DatabaseQueryTestView)
│   │   ├── auth.py          # 인증 관련 (Register, Login)
│   │   ├── likes.py         # 좋아요 관련 (MusicLike)
│   │   ├── search.py        # 검색 관련 (MusicSearch)
│   │   ├── music.py         # 음악 상세 관련 (MusicDetail)
│   │   ├── artists.py       # 아티스트 관련 (ArtistDetail, ArtistTracks, ArtistAlbums)
│   │   ├── playlogs.py      # 재생 기록 관련 (PlayLog)
│   │   ├── charts.py        # 차트 관련 (Chart 조회)
│   │   └── legacy.py        # 레거시 함수 기반 Views
│   │
│   ├── 📂 services/         # 외부 API 서비스
│   │   ├── __init__.py      # 모든 Service export
│   │   ├── itunes.py        # iTunes API 통합 (레거시 진입점, external/itunes.py로 위임)
│   │   ├── opensearch.py    # OpenSearch 클라이언트
│   │   ├── recommend_client.py  # 추천 서비스 클라이언트
│   │   ├── user_statistics.py  # 사용자 통계 서비스
│   │   ├── 📂 external/     # 공식 외부 API 통합
│   │   │   ├── spotify.py   # Spotify Web API (메타데이터·커버·아티스트 이미지·장르·ISRC)
│   │   │   ├── itunes.py    # iTunes Search API (30초 미리듣기, ISRC 미지원이라 검색 매칭)
│   │   │   └── lastfm.py    # Last.fm API (무드 태그, 곡-곡 유사도)
│   │   └── 📂 internal/     # 내부 도메인 서비스
│   │       ├── ai_music_service.py   # AI 음악 생성 도메인 로직
│   │       ├── mood_lexicon.py       # 무드 어휘 사전 (valence/arousal 역산)
│   │       ├── music_tag_service.py  # 음악 태그 매핑 서비스
│   │       ├── station_data.py       # 스테이션(플레이리스트) 데이터
│   │       └── user_statistics.py    # 사용자 통계 도메인 로직
│   │
│   ├── 📂 music_generate/   # AI 음악 생성 모듈
│   │   ├── __init__.py
│   │   ├── exceptions.py    # Suno API 예외 클래스
│   │   ├── parsers.py       # JSON 파서 (FlexibleJSONParser)
│   │   ├── services.py      # LlamaService, SunoAPIService
│   │   └── utils.py         # 유틸리티 함수 (장르 추출 등)
│   │
│   ├── 📂 templates/        # Django 템플릿 (HTML)
│   │   └── music/
│   │       ├── music_generator.html  # 음악 생성 페이지
│   │       ├── music_list.html       # 음악 목록 페이지
│   │       └── monitor.html          # 음악 모니터링 페이지
│   │
│   ├── parsers.py           # 파서 re-export (하위 호환성)
│   ├── services.py          # 레거시 서비스 (하위 호환성)
│   ├── serializers.py       # 레거시 시리얼라이저 (하위 호환성)
│   │
│   ├── 📂 tasks/            # Celery 비동기 작업
│   │   ├── charts.py        # 실시간/일일/AI 차트 갱신
│   │   ├── cleanup.py       # 재생기록/실시간차트 정리
│   │   ├── ai_music.py      # AI 음악 생성, Suno 웹훅 처리
│   │   ├── common.py        # 테스트용 태스크
│   │   ├── image_resize.py  # 이미지 리사이징
│   │   ├── metadata.py      # 아티스트 이미지 수집 (Spotify)
│   │   ├── enrichment.py    # 무드 태그·유사 곡 수집 (Last.fm)
│   │   ├── spotify_save.py  # Spotify 트랙 저장 (spotify_id 중복판정, ISRC 미리듣기, 후속 수집 트리거)
│   │   └── refresh.py       # 메타데이터 30일 주기 재수집 (refresh_stale_music)
│   │
│   ├── 📂 migrations/       # DB 마이그레이션
│   │   ├── 0001_initial.py
│   │   └── 0002_remove_music_lyrics_albums_release_date_and_more.py  # lyrics 컬럼 제거, spotify_id/isrc/release_date 등 추가
│   │
│   └── 📂 management/       # Django 관리 명령어
│       └── commands/
│           ├── graph_readiness.py    # GraphRAG 준비 상태 리포트 (music/tag/엣지 카운트, ready 플래그)
│           └── opensearch_setup.py   # OpenSearch 인덱스 생성/삭제/동기화
│
├── 🐳 Dockerfile             # Docker 이미지 빌드 설정
├── 🐳 docker-compose.yml     # 멀티 컨테이너 오케스트레이션
│
├── 📋 requirements.txt       # Python 패키지 의존성
├── 📋 README.md              # 프로젝트 설명서
├── 📋 TREE.md                # 파일 구조 (현재 파일)
├── 📋 ITUNES_API_GUIDE.md    # iTunes API 통합 가이드
├── 📋 FLOW_ARTIST_SEARCH_AND_TRACK_CLICK.md  # 아티스트 검색 → 곡 클릭 흐름 문서
├── 📋 TEST_USER_STATISTICS.md  # 사용자 통계 테스트 가이드
├── 📋 VIEW_STATISTICS.md     # 통계 뷰 가이드
│
├── 📂 monitoring/            # 모니터링 시스템 설정
│   ├── prometheus.yml        # Prometheus 설정
│   ├── loki.yml              # Loki 설정
│   ├── promtail.yml          # Promtail 설정
│   ├── rabbitmq_enabled_plugins  # RabbitMQ Prometheus 플러그인
│   └── 📂 grafana/           # Grafana 설정
│       ├── provisioning/     # 데이터소스/대시보드 프로비저닝
│       │   ├── datasources/datasources.yml
│       │   └── dashboards/dashboards.yml
│       └── dashboards/       # 대시보드 JSON 파일
│           ├── django-metrics.json
│           ├── system-overview.json
│           └── rabbitmq-metrics.json
│
├── 📂 lambda/                # AWS Lambda 함수
│   ├── image_resizer/        # 이미지 리사이징 Lambda 함수
│   │   ├── app.py            # Lambda 핸들러 (S3 이벤트 트리거)
│   │   └── requirements.txt  # Lambda 의존성
│   ├── template.yaml         # SAM 템플릿
│   └── README.md             # Lambda 배포 가이드
│
├── 🔒 .env                   # 환경 변수 (Git 제외)
├── 🔒 .env.example           # 환경 변수 템플릿 (팀 공유용)
└── 🔒 .gitignore             # Git 제외 파일 목록
```

## 📊 Phase 진행 상황

- [x] **Phase 1**: 로컬 올인원 환경 구축
- [x] **리팩토링**: config 폴더 구조로 정리
- [x] **Phase 2**: 인증 및 핵심 도메인 (User, Music, Playlist)
- [x] **Phase 3-1**: iTunes API 통합 (검색 우선 구조)
- [x] **앱 모듈화**: views/, serializers/, services/ 폴더 구조화
- [x] **Phase 3-2-1**: AI 음악 생성 (Suno API) 및 비동기 작업 (Celery)
- [x] **Phase 4**: 차트 API 구현 (실시간/일일/AI 차트)
- [x] **모니터링 시스템**: Prometheus, Grafana, Loki 통합 모니터링 구축
- [x] **음악 데이터 파이프라인 재구축**: 비공식 API(ytmusicapi/Deezer/Wikidata/LRCLIB/Lyrics.ovh) 제거 → Spotify+iTunes+Last.fm 공식 API 전환, 무드 태그/유사 곡 엣지 수집, 30일 주기 재수집
- [ ] **Phase 5**: 클라우드 이관 (AWS RDS, MQ, EC2)

## 📝 주요 변경사항

### 2026-01-13 - 차트 API 구현
- ✅ 실시간 차트 (10분마다, 최근 3시간 집계)
- ✅ 일일 차트 (매일 자정, 전날 전체 집계)
- ✅ AI 차트 (매일 자정, AI 곡만 집계)
- ✅ 재생 기록 API (POST /tracks/{id}/play)
- ✅ 차트 조회 API (GET /charts/{type})
- ✅ Celery Beat 스케줄 설정
- ✅ 데이터 정리 작업 (PlayLogs 90일, 실시간 차트 7일)

### 2026-01-13 - 앱 내부 모듈화
- ✅ `music/views/` 폴더 생성 (auth, likes, search, music, playlogs, charts)
- ✅ `music/serializers/` 폴더 생성 (base, music, search, auth, charts)
- ✅ `music/services/` 폴더 생성 (itunes)
- ✅ `__init__.py`에서 모든 클래스 export (기존 import 호환)
- ✅ 기능별 파일 분리로 협업 충돌 감소

### 2026-01-13 - iTunes API 통합
- ✅ iTunes Search API 서비스 구현
- ✅ 고급 검색 문법 지원 (검색어 + 태그: `아이유 # christmas`)
- ✅ '# ' (해시+공백) 패턴만 태그로 인식 (C#, I'm #1 등 안전 처리)
- ✅ 자동 DB 저장 (클릭 시 iTunes → DB 자동 저장)
- ✅ AI 필터링 (`exclude_ai` 파라미터)

### 2026-01-13 - AI 음악 생성 기능
- ✅ `music_generate/` 모듈 생성 (LlamaService, SunoAPIService)
- ✅ Llama를 통한 한국어 → 영어 프롬프트 변환
- ✅ Suno API 통합 (음악 생성, 상태 조회, 웹훅 처리)
- ✅ Celery 비동기 작업 (`generate_music_task`)
- ✅ 예외 처리 (크레딧 부족, 인증 실패 등)
- ✅ 웹 UI 템플릿 (생성, 목록, 모니터링 페이지)

### API 엔드포인트

**인증 및 사용자**
- `POST /api/v1/auth/users/` - 회원가입
- `POST /api/v1/auth/tokens/` - 로그인
- `POST /api/v1/auth/refresh/` - 토큰 갱신

**음악 검색 및 조회**
- `GET /api/v1/search?q={검색어}` - iTunes 기반 검색 (아티스트/앨범 자동 생성)
- `GET /api/v1/tracks/{itunes_id}` - 상세 조회 (자동 저장, 비동기 처리)
- `POST /api/v1/tracks/{music_id}/likes` - 좋아요 등록
- `DELETE /api/v1/tracks/{music_id}/likes` - 좋아요 취소

**아티스트 및 앨범**
- `GET /api/v1/artists/{artist_id}` - 아티스트 상세 조회
- `GET /api/v1/artists/{artist_id}/tracks` - 아티스트 곡 목록
- `GET /api/v1/artists/{artist_id}/albums` - 아티스트 앨범 목록

**AI 음악 생성**
- `POST /api/v1/generate/` - 음악 생성 (동기)
- `POST /api/v1/generate-async/` - 음악 생성 (비동기 - Celery)
- `GET /api/v1/task/{task_id}/` - 작업 상태 조회 (Celery)
- `GET /api/v1/suno-task/{task_id}/` - Suno API 작업 상태 조회
- `POST /api/v1/webhook/suno/` - Suno API 웹훅 (음악 생성 완료 콜백)

**사용자 통계**
- `GET /api/v1/statistics/` - 사용자 통계 요약
- `GET /api/v1/statistics/listening-time/` - 총 청취 시간
- `GET /api/v1/statistics/top-genres/` - 인기 장르
- `GET /api/v1/statistics/top-artists/` - 인기 아티스트
- `GET /api/v1/statistics/top-tags/` - 인기 태그
- `GET /api/v1/statistics/ai-generation/` - AI 생성 통계

**테스트 엔드포인트 (모니터링용)**
- `GET /api/v1/test/error?code={500}&rate={0.5}` - 에러율 테스트
- `GET /api/v1/test/db?count={10}&type={all|select}` - DB 쿼리 테스트

**웹 페이지 (UI)**
- `GET /music/generator/` - 음악 생성 페이지
- `GET /music/list/` - 음악 목록 페이지
- `GET /music/monitor/{music_id}/` - 음악 모니터링 페이지

### 2026-01-13 - 리팩토링 완료
- ✅ `config/` 폴더 생성 및 설정 파일 이동
- ✅ `settings.py`, `urls.py`, `wsgi.py` → `config/`로 이동
- ✅ `asgi.py` 생성 (비동기 지원)
- ✅ `celery_app.py` → `config/celery.py`로 이동
- ✅ 모든 import 경로 업데이트 (`settings` → `config.settings`)

### 2026-01-15 - 모니터링 시스템 구축
- ✅ Prometheus, Grafana, Loki 통합 모니터링 스택 구축
- ✅ Django 메트릭 수집 (django-prometheus)
- ✅ RabbitMQ Prometheus 플러그인 활성화
- ✅ Grafana 대시보드 3개 자동 프로비저닝
  - Django Application Metrics (7개 패널)
  - System Overview (9개 패널)
  - RabbitMQ Metrics (10개 패널)
- ✅ 테스트 엔드포인트 추가
  - `/api/v1/test/error` - 에러율 테스트
  - `/api/v1/test/db` - DB 쿼리 테스트
- ✅ 모든 대시보드 쿼리에 "No data" 방지 처리 (`or vector(0)`)

### 2026-01-16 - 아티스트/앨범 이미지 S3 업로드 및 리사이징 (⚠️ 2026-07 파이프라인 개편으로 대체됨, 아래 참고)
- ✅ 아티스트 이미지 자동 수집 (Wikidata → Deezer fallback)
- ✅ 앨범 이미지 자동 수집 (iTunes 이미지 URL)
- ✅ S3 업로드 유틸리티 구현 (`music/utils/s3_upload.py`)
- ✅ AWS Lambda 이미지 리사이징 함수 구현
  - 아티스트: 원형 228x228, 208x208 / 사각형 220x220
  - 앨범: 사각형 220x220
- ✅ 검색 시 아티스트/앨범 자동 생성 및 이미지 수집
- ✅ 곡 클릭 시 Music/Album 자동 생성 및 이미지 수집
- ✅ Wikipedia 403 에러 해결 (User-Agent 헤더 추가)
- ✅ 이미지 마이그레이션 명령어 추가
  - `migrate_images_to_s3` - 기존 이미지 S3 마이그레이션
  - `update_resized_image_urls` - 리사이징된 이미지 URL 업데이트
- ✅ 전체 흐름 문서화 (`FLOW_ARTIST_SEARCH_AND_TRACK_CLICK.md`)

### 2026-07-09~10 - 음악 데이터 파이프라인 재구축 (공식 API 전환)
- ✅ 비공식 API(ytmusicapi, Deezer, Wikidata, LRCLIB, Lyrics.ovh) 전면 제거
- ✅ **Spotify Web API** 통합: 메타데이터·커버 아트·아티스트 이미지·장르·ISRC 수집 (`music/services/external/spotify.py`)
- ✅ **iTunes Search API** 기반 30초 미리듣기 조회로 전환 (ISRC lookup 미지원 확인 후 검색 매칭으로 변경, `search_preview`)
- ✅ **Last.fm API** 통합: 무드 태그 수집 → 무드 어휘 사전으로 valence/arousal 역산, 곡-곡 유사 엣지(`music_similar` 테이블) 수집 (`music/services/external/lastfm.py`)
- ✅ `Music` 모델: `lyrics` 컬럼 제거, `spotify_id`(unique)·`isrc` 컬럼 추가 (`Albums.release_date` 등도 함께 정리)
- ✅ 검색/상세/재생 뷰를 `spotify_id` 기반으로 전환
- ✅ 가사(lyrics) 관련 기능·필드 전면 제거 (시리얼라이저, 뷰, 태스크)
- ✅ 메타데이터 30일 주기 재수집 Celery Beat 태스크 추가 (`refresh_stale_music`, Spotify/Last.fm 데이터 신선도 조항 대응)
- ✅ `graph_readiness` 관리 명령어 추가 (GraphRAG 준비 상태: music/tag/엣지 카운트, `ready` 플래그)
- ✅ S3 이미지 업로드 시그널 및 관련 관리 명령어(`migrate_images_to_s3`, `update_resized_image_urls`) 제거
