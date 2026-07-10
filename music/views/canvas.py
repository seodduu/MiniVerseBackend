"""Canvas GraphRAG API."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..serializers.canvas import CanvasGraphRagResponseSerializer
from ..services.internal.canvas_graphrag_service import CanvasGraphRagService


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
