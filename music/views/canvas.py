"""Canvas GraphRAG API."""

from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..serializers.canvas import (
    CanvasAnswerRequestSerializer,
    CanvasAnswerResponseSerializer,
    CanvasAskRequestSerializer,
    CanvasAskResponseSerializer,
    CanvasGraphRagResponseSerializer,
)
from ..services.internal.canvas_graphrag_service import CanvasGraphRagService
from ..services.internal.canvas_nlq_service import CanvasNlqService


class CanvasGraphRagView(APIView):
    """Return hybrid graph-ranked tracks for Canvas tag queries."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="캔버스 GraphRAG 태그 검색",
        description=(
            "곡-태그 직접 연결, 유사곡, 아티스트 장르, 무드 좌표를 "
            "결합한 캔버스 검색 결과를 반환합니다."
        ),
        parameters=[
            OpenApiParameter(
                name="tags",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="쉼표로 구분한 태그 목록. 예: happy,upbeat",
                required=True,
            ),
            OpenApiParameter(
                name="limit",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="반환할 최대 결과 수. 기본 120, 최대 150",
                required=False,
            ),
        ],
        responses={200: CanvasGraphRagResponseSerializer},
        tags=["캔버스"],
    )
    def get(self, request):
        raw_tags = request.query_params.get("tags") or request.query_params.get("tag") or ""
        result = CanvasGraphRagService.search([raw_tags], request.query_params.get("limit"))
        serializer = CanvasGraphRagResponseSerializer(data=result)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CanvasAskView(APIView):
    """자연어 질의를 LLM으로 태그 추출한 뒤 기존 GraphRAG 검색을 실행한다.

    ② 그래프 검색·랭킹 코어(``CanvasGraphRagService``)는 무변경으로 재사용하고,
    ①(질의 해석)만 이 View에서 얇게 얹는다.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="캔버스 자연어 질의 → 태그 추출 + GraphRAG 검색",
        description=(
            "자연어 질의를 LLM으로 해석해 태그를 추출한 뒤, 기존 "
            "CanvasGraphRagService 검색을 실행합니다. LLM 실패 시 "
            "쉼표 분리 exact-match 폴백을 사용합니다."
        ),
        request=CanvasAskRequestSerializer,
        responses={200: CanvasAskResponseSerializer},
        tags=["캔버스"],
    )
    def post(self, request):
        request_serializer = CanvasAskRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        query = request_serializer.validated_data["query"]
        limit = request_serializer.validated_data.get("limit")

        extracted_tags, source = CanvasNlqService.extract_tags(query)

        # 추출 태그가 빈 리스트여도 그대로 넘겨 기존 서비스 로직이
        # missing_query/no_match 계열을 자연스럽게 내도록 한다 (신규 분기 추가 금지).
        result = CanvasGraphRagService.search(extracted_tags, limit)
        result["interpretation"] = {
            "original_query": query,
            "extracted_tags": extracted_tags,
            "source": source,
        }

        serializer = CanvasAskResponseSerializer(data=result)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CanvasAnswerView(APIView):
    """검색을 무상태로 재실행한 뒤 근거 기반 자연어 답변을 생성한다."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="캔버스 자연어 질의 → 근거 기반 답변 생성",
        description=(
            "검색을 재실행(무상태)한 뒤 상위 10곡을 압축한 컨텍스트로 "
            "LLM 답변을 생성합니다. LLM 실패/타임아웃 또는 검색 결과 0곡이면 "
            "HTTP 200으로 answer: null과 reason을 반환합니다."
        ),
        request=CanvasAnswerRequestSerializer,
        responses={200: CanvasAnswerResponseSerializer},
        tags=["캔버스"],
    )
    def post(self, request):
        request_serializer = CanvasAnswerRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        query = request_serializer.validated_data["query"]
        tags = request_serializer.validated_data["tags"]

        result = CanvasGraphRagService.search(tags, None)
        items = result.get("items") or []
        if not items:
            payload = {"answer": None, "reason": "no_results"}
            serializer = CanvasAnswerResponseSerializer(data=payload)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        answer = CanvasNlqService.generate_answer(query, tags, items)
        if answer is None:
            payload = {"answer": None, "reason": "llm_unavailable"}
            serializer = CanvasAnswerResponseSerializer(data=payload)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        payload = {"answer": answer, "model": settings.LLAMA_MODEL_NAME}
        serializer = CanvasAnswerResponseSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
