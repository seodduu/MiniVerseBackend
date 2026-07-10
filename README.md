## BACKEND 레포지스토리 입니다

### 🎵 음악 데이터 파이프라인 (Spotify + iTunes + Last.fm)

비공식 API(ytmusicapi, Deezer, Wikidata, LRCLIB, Lyrics.ovh 등) 의존을 제거하고,
공식 API 3종으로 음악 데이터를 수집·저장합니다.

- **Spotify Web API**: 곡 메타데이터, 커버 아트, 아티스트 이미지, 장르, ISRC
- **iTunes Search API**: 30초 미리듣기(preview) URL (ISRC 조회는 미지원이라 검색으로 매칭)
- **Last.fm API**: 무드 태그(→ valence/arousal 역산), 곡-곡 유사(`music_similar`) 엣지

수집된 데이터는 30일 주기로 재수집(`refresh_stale_music` Celery Beat 태스크)되어
Spotify/Last.fm 데이터 신선도 조항을 준수합니다.

#### 환경 변수 설정

`.env` 파일에 다음 환경 변수를 추가하세요:

```bash
# Spotify Web API (Client Credentials Flow)
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# Last.fm API
LASTFM_API_KEY=your_lastfm_api_key
```

#### GraphRAG 준비 상태 확인

곡/태그/엣지 데이터가 GraphRAG 파이프라인을 구동하기에 충분한지 확인합니다.

```bash
python manage.py graph_readiness
```

출력 예시:

```
music_count=30
tag_count=10
music_tag_edge_count=30
music_similar_edge_count=0
tracks_with_images=30
ready=true
```

- `music_count`, `tag_count`, `music_tag_edge_count`, `music_similar_edge_count`: 각 테이블 레코드 수
- `tracks_with_images`: 앨범 커버 이미지가 있는 곡 수
- `ready`: 곡·태그·곡-태그 엣지가 모두 1건 이상이면 `true`

### 🔍 AWS OpenSearch 검색 기능

프로젝트에 AWS OpenSearch 기반 음악 검색 기능이 추가되었습니다!

#### 환경 변수 설정

`.env` 파일에 다음 환경 변수를 추가하세요:

```bash
# AWS OpenSearch 설정
OPENSEARCH_HOST=your-opensearch-domain.region.es.amazonaws.com
OPENSEARCH_PORT=443
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=your-opensearch-password
OPENSEARCH_USE_SSL=True
OPENSEARCH_VERIFY_CERTS=True
OPENSEARCH_INDEX_PREFIX=music
```

#### 패키지 설치

```bash
pip install -r requirements.txt
```

#### 인덱스 생성 및 데이터 동기화

```bash
# 인덱스 리셋 (삭제 → 생성 → 동기화)
python manage.py opensearch_setup --reset

# 또는 개별 실행
python manage.py opensearch_setup --create  # 인덱스 생성
python manage.py opensearch_setup --sync    # 데이터 동기화
python manage.py opensearch_setup --delete  # 인덱스 삭제
```

#### API 사용

```bash
# OpenSearch 검색
curl "http://localhost:8000/api/v1/search/opensearch?q=아이유&sort_by=popularity"

# 인덱스 생성
curl -X POST http://localhost:8000/api/v1/search/opensearch/index

# 데이터 동기화
curl -X POST http://localhost:8000/api/v1/search/opensearch/sync
```

자세한 내용은 [OpenSearch 가이드](./docs/opensearch.md)를 참조하세요.
