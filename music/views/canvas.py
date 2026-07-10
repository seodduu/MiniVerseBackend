"""
/canvas GraphRAG Views.
"""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema

from ..serializers.canvas import CanvasGraphRagResponseSerializer
from ..services.internal.canvas_graphrag_service import CanvasGraphRagService


class CanvasGraphRagView(APIView):
    """
    /canvas 태그 검색용 GraphRAG 1차 엔드포인트.

    1차 버전은 music_tags의 직접 태그 연결 점수를 relevance로 사용한다.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="캔버스 GraphRAG 태그 검색",
        description="""
        /canvas 화면에서 사용할 GraphRAG 검색 결과를 반환합니다.

        1차 버전은 곡-태그 연결(`music_tags.score`)을 기반으로 `relevance_score`와
        `visual_weight`를 계산합니다. 데이터가 없으면 실패 대신 명시적인 빈 상태를 반환합니다.
        """,
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
        tag_values = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
        limit = request.query_params.get("limit")

        result = CanvasGraphRagService.search(tag_values, limit)
        serializer = CanvasGraphRagResponseSerializer(data=result)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
