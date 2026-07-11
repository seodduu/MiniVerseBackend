# Canvas 자연어 질의응답 (GraphRAG "G" 완성) 설계

## 1. 목적

현재 `/api/v1/canvas/graphrag`는 GraphRAG라는 이름을 쓰지만 실제로는
**Retrieval(그래프 검색·랭킹)만 수행하고 Generation이 없다.**
이 설계는 검색 파이프라인 앞뒤에 로컬 LLM 레이어를 붙여
**자연어 질의 → 그래프 검색 → 근거 기반 자연어 답변**의 완전한 GraphRAG 루프를 만든다.

```text
"비 오는 날 운전할 때 들을 노래 있어?"
   │
   ▼ ① LLM: 질의 해석 (자연어 → 태그, 어휘 제약)
tags = ["chill", "mellow", "relaxing"]
   │
   ▼ ② 그래프 검색·랭킹 (기존 CanvasGraphRagService — 무변경)
items + explanations + score_breakdown
   │
   ▼ ③ LLM: 답변 생성 (질문 원문 + 그래프 경로 → 자연어, grounding)
"비 오는 날 운전이라면 차분한 결이 좋겠네요. 'chill'의 중심에는 …"
```

- 검색 코어(②)는 계약·코드 모두 무변경. LLM은 입구(①)·출구(③)의 얇은 어댑터다.
- 기존 태그 검색 엔드포인트는 그대로 유지한다 (파워유저/폴백 경로).

## 2. 전제 — 실호출로 검증된 사실 (2026-07-12)

프로젝트 원칙(공식·단순·실호출 검증)에 따라 설계 확정 전에 실제 환경에서 검증했다.

| 항목 | 값 | 확인 방법 |
|---|---|---|
| LLM 서버 | Ollama `http://{WINDOWS_LLAMA_IP}:11434` (현재 `host.docker.internal`) | `/api/tags` 실호출 OK |
| 모델 | `LLAMA_MODEL_NAME` env = `qwen3.6:35b` (settings 기본값 `llama3.1:…`과 다름 — **env가 진실**) | 컨테이너 env 확인 |
| 태그 어휘 | **22개** (`happy`, `chill`, `sad`, …) — 전체를 프롬프트에 주입 가능 | DB 카운트 |
| 그래프 엣지 | `music_tags` 316개 (시드 98곡) | DB 카운트 |
| ① 지연 | 웜 **0.8~1.3s**, 콜드(모델 로드) **~13s** | 실호출 3건 |
| ① 정확도 | 3/3 질의가 어휘 내 태그로 유효 JSON 매핑 | 아래 표 |

실호출 결과:

| 질의 | 추출 태그 |
|---|---|
| 비 오는 날 운전할 때 들을 노래 있어? | `["chill", "mellow", "relaxing"]` |
| 여름 밤 드라이브에 어울리는 신나는 곡 | `["summer", "upbeat", "happy"]` |
| 우울한 날 위로가 되는 노래 | `["sad", "emotional", "melancholic"]` |

주의: `qwen3.6`는 thinking 모델 계열이므로 요청에 **`think: false`** 를 명시해야
추론 텍스트 없이 JSON만 받는다 (검증 시 확인).

## 3. 아키텍처 — 응답 2분할

캔버스는 ③(답변 생성)을 기다리지 않는다. ②가 끝난 시점에 즉시 응답해
캔버스를 먼저 그리고, ③은 프론트가 두 번째 요청으로 비동기로 받는다.

```text
프론트                          백엔드                          Ollama
  │ POST /canvas/ask {query}
  │────────────────────────────▶│
  │                             │ ① 어휘 주입 + few-shot → 태그 추출
  │                             │──────────────────────────────▶│
  │                             │◀── ["chill","mellow"] ────────│
  │                             │ ② CanvasGraphRagService.search()
  │◀─ tags + items (기존 계약) ──│
  │   ★ 캔버스 즉시 렌더 + 태그 칩  │
  │                             │
  │ POST /canvas/answer {query, tags}
  │────────────────────────────▶│ ②' 검색 재실행(무상태) → 컨텍스트 압축
  │                             │ ③ grounding + few-shot → 답변 생성
  │                             │──────────────────────────────▶│
  │                             │◀────────── 자연어 답변 ─────────│
  │◀─ {answer} ─────────────────│
  │   답변 패널 채움               │
```

`/answer`가 검색을 **재실행**하는 이유: 데이터가 소량(98곡)이라 검색 비용이
밀리초 단위 → 상태 저장·캐시 정합성 관리보다 무상태 재실행이 단순하다.

## 4. API 설계

### 4.1 `POST /api/v1/canvas/ask`

질의 해석 + 그래프 검색. permission은 기존 canvas와 동일(`AllowAny`).

요청:
```json
{ "query": "비 오는 날 운전할 때 들을 노래 있어?", "limit": 120 }
```

응답 = **기존 `CanvasGraphRagResponseSerializer` 계약 그대로** + `interpretation` 필드 추가:
```json
{
  "status": "ok",
  "interpretation": {
    "original_query": "비 오는 날 운전할 때 들을 노래 있어?",
    "extracted_tags": ["chill", "mellow", "relaxing"],
    "source": "llm"            // "llm" | "fallback_direct"
  },
  "query": { ... },            // 이하 기존 graphrag 응답 그대로
  "items": [ ... ],
  "meta": { ... }
}
```

### 4.2 `POST /api/v1/canvas/answer`

근거 기반 답변 생성. 비동기 두 번째 호출용.

요청:
```json
{ "query": "비 오는 날 운전할 때 들을 노래 있어?", "tags": ["chill", "mellow", "relaxing"] }
```

응답:
```json
{ "answer": "비 오는 날 운전이라면 차분한 결이 좋겠네요. …", "model": "qwen3.6:35b" }
```
실패 시: `{ "answer": null, "reason": "llm_unavailable" }` (HTTP 200 — 캔버스는 이미 떠 있으므로 무해 degrade).

### 4.3 기존 `GET /canvas/graphrag` — 무변경

태그 칩 수정 후 재검색은 이 기존 엔드포인트를 그대로 사용한다.

## 5. 프롬프트 설계

### 5.1 ① 태그 추출 — 형식 강제가 목적

```text
system:
  You map a Korean music request to tags.
  Choose ONLY from this list: {DB에서 로드한 22개 어휘, 쉼표 구분}.
  Output ONLY a JSON array of 1-3 tags, nothing else. If nothing fits, output [].
  Example: "슬플 때 듣는 노래" -> ["sad", "melancholic"]
  Example: "신나는 파티 음악 틀어줘" -> ["party", "energetic", "upbeat"]
  Example: "주식 알려줘" -> []
user: {query}
options: temperature 0.1, num_predict 40, think: false
```

- 어휘는 하드코딩하지 않고 **요청 시 DB에서 로드** (`Tags.objects.filter(is_deleted=False)`).
  22개 규모라 매 요청 주입 부담 없음. 태그가 늘어도 자동 반영.
- 파싱: 응답에서 JSON 배열 추출 → 어휘 밖 태그는 **드롭** → 남은 것이 0개면 폴백(§7).
- 음악과 무관한 질의는 `[]` 를 출력하도록 few-shot에 반례 포함.

### 5.2 ③ 답변 생성 — grounding + 톤 일관성이 목적

```text
system:
  당신은 음악 큐레이터다. 사용자의 질문과 그래프 검색 결과를 바탕으로 답한다.
  규칙:
  1. 아래 [검색 결과]에 있는 곡만 언급한다. 목록에 없는 곡을 지어내지 않는다.
  2. 3~4문장, 한국어. 형식: 무드 요약 → 중심 곡과 발견 이유 → 이어 들을 곡 제안.
  3. 발견 이유는 경로 정보(직접 태그/유사곡/무드 근접)를 근거로 말한다.
  Example: (질문/컨텍스트/답변 완성 예시 1~2개 고정 삽입)
user:
  [질문] {query}
  [해석된 태그] {tags}
  [검색 결과] (상위 N=10, 압축)
  - {곡명} — {아티스트} | 신호: direct_tag(0.82) | 경로: 'chill' 태그 직접 연결
  - {곡명} — {아티스트} | 신호: similar(0.41) | 경로: 곡 A의 유사곡
  ...
options: temperature 0.4, think: false
```

- 컨텍스트는 **상위 10곡, 곡당 1줄**로 압축 — `music_name`, `artist_name`,
  최고 신호 1개(`score_breakdown` 최대값), 대표 경로 1개(`explanations[0]` 요약).
- grounding 규칙 1이 이 프롬프트의 핵심. RAG의 신뢰성이 여기서 갈린다.

## 6. 백엔드 구현

| 구성요소 | 파일 | 내용 |
|---|---|---|
| LLM 클라이언트 + 서비스 | `music/services/internal/canvas_nlq_service.py` (신규) | `CanvasNlqService`: `extract_tags(query)`, `generate_answer(query, tags, items)` |
| View | `music/views/canvas.py` (추가) | `CanvasAskView`, `CanvasAnswerView` |
| Serializer | `music/serializers/canvas.py` (추가) | `CanvasAskRequest/Response`, `CanvasAnswerRequest/Response` (기존 클래스 재사용) |
| URL | `music/urls.py` (추가) | `canvas/ask`, `canvas/answer` |
| 테스트 | `music/tests/test_canvas_nlq.py` (신규) | LLM은 mock, 파싱·폴백·계약 검증 |

구현 규칙:

- **LLM 호출은 Ollama `/api/chat`에 `requests`로 직접 호출**한다.
  검증을 raw API로 했고, `think: false` 같은 옵션 제어가 명시적이며,
  LangChain 의존을 늘리지 않는다 (기존 `LlamaService`는 Suno 전용이라 재사용하지 않고,
  `settings.WINDOWS_LLAMA_IP` / `settings.LLAMA_MODEL_NAME` 설정만 공유).
- 요청 옵션에 **`keep_alive: "30m"`** 을 줘 콜드 스타트(~13s)를 줄인다.
- 타임아웃: ① 30s / ③ 60s (`requests` timeout). 초과 시 §7 폴백.
- ③ 결과는 Django cache에 `key = sha1(normalized_query + sorted_tags)`, TTL 1h로 캐시.

## 7. 실패 처리 매트릭스

| 상황 | ① `/ask` 동작 | 프론트 동작 |
|---|---|---|
| LLM 다운/타임아웃 | **폴백**: query를 쉼표 분리해 어휘와 exact match 시도 (`source: "fallback_direct"`), 매치 0개면 `data_state: "llm_unavailable"` | 태그 직접 입력 모드 안내 |
| LLM이 유효하지 않은 출력 | 어휘 밖 태그 드롭 후 0개면 위와 동일 폴백 | 동일 |
| 추출 태그 `[]` (무관한 질의) | 기존 `no_match` 계열 응답 + `extracted_tags: []` | "질문을 이해하지 못했어요" + 예시 질의 제안 |
| 상황 | ③ `/answer` 동작 | 프론트 동작 |
| LLM 실패/타임아웃 | `{"answer": null, "reason": "llm_unavailable"}` (HTTP 200) | 답변 패널 숨김 — **캔버스는 무영향** |
| 검색 결과 0곡 | `{"answer": null, "reason": "no_results"}` | 동일 |

기존 graceful degradation 철학 유지: **LLM이 전부 죽어도 태그 검색 캔버스는 동작한다.**

## 8. 프론트 구현 (`MuniVerseFrontend`)

- `src/api/music.ts`: `askCanvas(query, limit)`, `getCanvasAnswer(query, tags)` 추가.
- `InteractiveCanvasPage`:
  1. 검색창이 자유 텍스트 허용 (기존 쉼표 태그 입력도 그대로 동작 — 쉼표 구분 어휘
     매치면 기존 `/graphrag` 직행, 아니면 `/ask`).
  2. 응답의 `extracted_tags`를 **수정 가능한 칩**으로 노출 — 칩 편집 시 기존
     `/graphrag`로 재검색 (① LLM의 해석을 투명하게, 오해석은 사용자가 교정).
  3. items로 캔버스 즉시 렌더 후, `/answer`를 비동기 호출해 답변 패널을 채움
     (로딩 중 "답변 생성 중…" 표시, `null`이면 패널 숨김).
- 콜드 스타트 대비: `/ask` 로딩 상태에 "질문을 해석하는 중…" 문구 (최대 ~15s 허용).

## 9. 비범위 (Non-goals)

- 멀티턴 대화/히스토리 없음 — 질의 1건 = 응답 1건.
- 벡터 검색/임베딩 없음 — 검색은 기존 관계형 그래프 그대로.
- 새 DB 테이블 없음 — 전 과정 무상태 (캐시는 Django cache).
- 곡별 상세 설명 생성(옵션 2)은 이번 범위 밖 — 후속 후보.

## 10. 구현 순서와 검증 계획

1. **백엔드 ①+②** — `CanvasNlqService.extract_tags` + `/ask` → 실호출 검증
   (한국어 질의 5종: 상황형/무드형/무관질의/장난질의/영어질의).
2. **백엔드 ③** — `generate_answer` + `/answer` → 실호출로 grounding 확인
   (답변에 검색 결과 밖 곡이 없는지 육안 검증).
3. **프론트** — 검색창/칩/답변 패널 연동.
4. **mock 테스트** — LLM mock으로 파싱·폴백·계약 회귀 테스트 고정.

각 단계는 실호출 검증을 통과한 뒤 다음으로 넘어간다 (프로젝트 원칙).
