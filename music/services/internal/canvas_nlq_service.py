"""캔버스 자연어 질의응답을 위한 LLM 어댑터 서비스.

자연어 질의 → 태그 추출(①) / 검색 결과 → 자연어 답변 생성(③)을 담당한다.
그래프 검색 코어(②, ``CanvasGraphRagService``)는 이 서비스가 건드리지 않는다.

Ollama ``/api/chat``을 ``requests``로 직접 호출한다 (LangChain 미사용).
``qwen3.6`` 계열은 thinking 모델이므로 모든 요청에 ``think: false``를 명시해야
추론 텍스트가 답변에 섞이지 않는다.
"""

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.conf import settings
from django.core.cache import cache

from ...models import Tags

# ① 태그 추출 타임아웃 (콜드 스타트 최대 ~13s 고려한 여유)
EXTRACT_TAGS_TIMEOUT = 30
# ③ 답변 생성 타임아웃 (10곡 컨텍스트 + 3~4문장 생성)
GENERATE_ANSWER_TIMEOUT = 60

# ③ 답변 캐시 TTL (1시간)
ANSWER_CACHE_TTL = 3600

# ③ 컨텍스트에 포함할 최대 곡 수
MAX_CONTEXT_ITEMS = 10


class CanvasNlqService:
    """캔버스 자연어 질의응답을 위한 LLM 클라이언트."""

    @staticmethod
    def _chat_url() -> str:
        return f"http://{settings.WINDOWS_LLAMA_IP}:11434/api/chat"

    # ------------------------------------------------------------------
    # ① 태그 추출
    # ------------------------------------------------------------------
    @classmethod
    def extract_tags(cls, query: str) -> Tuple[List[str], str]:
        """자연어 질의를 어휘 내 태그 목록으로 변환한다.

        Returns:
            (tags, source) — source는 "llm" 또는 "fallback_direct".
        """
        vocabulary = list(
            Tags.objects.filter(is_deleted=False).values_list("tag_key", flat=True)
        )
        if not vocabulary:
            return cls._fallback_extract(query, vocabulary)

        llm_tags = cls._extract_tags_via_llm(query, vocabulary)
        if llm_tags:
            return llm_tags, "llm"

        # LLM 실패/무효출력/어휘 밖만 있어서 0개 → 폴백
        return cls._fallback_extract(query, vocabulary)

    @classmethod
    def _extract_tags_via_llm(cls, query: str, vocabulary: List[str]) -> Optional[List[str]]:
        system_prompt = (
            "You map a Korean music request to tags.\n"
            f"Choose ONLY from this list: {', '.join(vocabulary)}.\n"
            "Output ONLY a JSON array of 1-3 tags, nothing else. If nothing fits, output [].\n"
            'Example: "슬플 때 듣는 노래" -> ["sad", "melancholic"]\n'
            'Example: "신나는 파티 음악 틀어줘" -> ["party", "energetic", "upbeat"]\n'
            'Example: "주식 알려줘" -> []'
        )
        payload = {
            "model": settings.LLAMA_MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "options": {"temperature": 0.1, "num_predict": 40},
        }
        try:
            response = requests.post(
                cls._chat_url(), json=payload, timeout=EXTRACT_TAGS_TIMEOUT
            )
            response.raise_for_status()
        except requests.exceptions.RequestException:
            return None

        content = cls._extract_message_content(response)
        if content is None:
            return None

        parsed = cls._parse_tag_array(content)
        if parsed is None:
            return None

        vocab_set = {tag for tag in vocabulary}
        valid_tags = [tag for tag in parsed if tag in vocab_set][:3]
        return valid_tags if valid_tags else None

    @staticmethod
    def _extract_message_content(response: requests.Response) -> Optional[str]:
        try:
            data = response.json()
        except ValueError:
            return None
        message = data.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            return None
        return content

    @staticmethod
    def _parse_tag_array(content: str) -> Optional[List[str]]:
        """모델 출력에서 JSON 배열을 추출해 파싱한다."""
        match = re.search(r"\[.*?\]", content, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except (ValueError, TypeError):
            return None
        if not isinstance(parsed, list):
            return None
        return [str(tag).strip() for tag in parsed if isinstance(tag, (str,)) and str(tag).strip()]

    @staticmethod
    def _fallback_extract(query: str, vocabulary: List[str]) -> Tuple[List[str], str]:
        """LLM 실패 시 쉼표 분리 후 어휘와 exact match 하는 폴백."""
        vocab_by_norm = {tag.strip().casefold(): tag for tag in vocabulary}
        matched: List[str] = []
        seen = set()
        for part in query.split(","):
            normalized = part.strip().casefold()
            tag = vocab_by_norm.get(normalized)
            if tag and tag not in seen:
                matched.append(tag)
                seen.add(tag)
        return matched[:3], "fallback_direct"

    # ------------------------------------------------------------------
    # ③ 답변 생성
    # ------------------------------------------------------------------
    @classmethod
    def generate_answer(
        cls, query: str, tags: List[str], items: List[Dict[str, Any]]
    ) -> Optional[str]:
        """검색 결과를 근거로 grounding된 자연어 답변을 생성한다.

        실패(LLM 다운/타임아웃/파싱 불가) 시 None을 반환한다.
        """
        cache_key = cls._answer_cache_key(query, tags)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        context_lines = cls._build_context_lines(items)
        answer = cls._generate_answer_via_llm(query, tags, context_lines)
        if answer:
            cache.set(cache_key, answer, ANSWER_CACHE_TTL)
        return answer

    @classmethod
    def _generate_answer_via_llm(
        cls, query: str, tags: List[str], context_lines: List[str]
    ) -> Optional[str]:
        system_prompt = (
            "당신은 음악 큐레이터다. 사용자의 질문과 그래프 검색 결과를 바탕으로 답한다.\n"
            "규칙:\n"
            "1. 아래 [검색 결과]에 있는 곡만 언급한다. 목록에 없는 곡을 지어내지 않는다.\n"
            "2. 3~4문장, 한국어. 형식: 무드 요약 → 중심 곡과 발견 이유 → 이어 들을 곡 제안.\n"
            "3. 발견 이유는 경로 정보(직접 태그/유사곡/무드 근접)를 근거로 말한다.\n"
            "Example:\n"
            "[질문] 비 오는 날 운전할 때 들을 노래 있어?\n"
            "[해석된 태그] chill, mellow, relaxing\n"
            "[검색 결과]\n"
            "- Night Drive — Luna Bay | 신호: direct_tag(0.82) | 경로: 'chill' 태그 직접 연결\n"
            "- Slow Rain — Kite Club | 신호: similar(0.41) | 경로: Night Drive의 유사곡\n"
            "답변: 비 오는 날 운전이라면 차분하고 여유로운 결이 좋겠네요. "
            "중심이 되는 곡은 'Night Drive'로, 'chill' 태그와 직접 연결되어 있어 이 무드의 핵심을 보여줍니다. "
            "이어서 'Night Drive'의 유사곡인 'Slow Rain'을 들어보시면 비슷한 감성을 이어갈 수 있어요."
        )
        context_block = "\n".join(context_lines) if context_lines else "(검색 결과 없음)"
        user_prompt = (
            f"[질문] {query}\n"
            f"[해석된 태그] {', '.join(tags)}\n"
            f"[검색 결과]\n{context_block}"
        )
        payload = {
            "model": settings.LLAMA_MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "options": {"temperature": 0.4},
        }
        try:
            response = requests.post(
                cls._chat_url(), json=payload, timeout=GENERATE_ANSWER_TIMEOUT
            )
            response.raise_for_status()
        except requests.exceptions.RequestException:
            return None

        content = cls._extract_message_content(response)
        if content is None:
            return None
        stripped = content.strip()
        return stripped or None

    @staticmethod
    def _build_context_lines(items: List[Dict[str, Any]]) -> List[str]:
        """상위 N곡을 곡당 1줄로 압축한다.

        각 줄: 곡명 — 아티스트 | 신호: 최댓값 신호(값) | 경로: 대표 설명 1개.
        """
        lines: List[str] = []
        for item in items[:MAX_CONTEXT_ITEMS]:
            music_name = item.get("music_name") or "(제목 없음)"
            artist_name = item.get("artist_name") or "(아티스트 미상)"
            breakdown = item.get("score_breakdown") or {}
            if breakdown:
                top_signal, top_value = max(breakdown.items(), key=lambda kv: kv[1])
            else:
                top_signal, top_value = "unknown", 0.0
            explanations = item.get("explanations") or []
            reason = explanations[0].get("reason") if explanations else ""
            lines.append(
                f"- {music_name} — {artist_name} | 신호: {top_signal}({top_value:.2f}) | 경로: {reason}"
            )
        return lines

    @staticmethod
    def _answer_cache_key(query: str, tags: List[str]) -> str:
        normalized_query = query.strip().casefold()
        joined_tags = ",".join(sorted(tags))
        raw = f"{normalized_query}|{joined_tags}"
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        return f"canvas_nlq_answer:{digest}"
