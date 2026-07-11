"""Canvas GraphRAG response serializers."""

from rest_framework import serializers


class CanvasGraphRagResolvedTagSerializer(serializers.Serializer):
    tag_id = serializers.IntegerField()
    tag_key = serializers.CharField(allow_blank=True)
    tag_name = serializers.CharField(allow_blank=True)


class CanvasGraphRagQuerySerializer(serializers.Serializer):
    tags = serializers.ListField(child=serializers.CharField())
    resolved_tags = CanvasGraphRagResolvedTagSerializer(many=True)
    unresolved_tags = serializers.ListField(child=serializers.CharField())


class CanvasGraphRagMatchedTagSerializer(serializers.Serializer):
    tag_key = serializers.CharField(allow_blank=True)
    tag_name = serializers.CharField(allow_blank=True)
    score = serializers.FloatField()


class CanvasGraphRagExplanationSerializer(serializers.Serializer):
    type = serializers.CharField()
    path = serializers.ListField(child=serializers.CharField())
    weight = serializers.FloatField()
    reason = serializers.CharField()


class CanvasGraphRagScoreBreakdownSerializer(serializers.Serializer):
    direct_tag = serializers.FloatField()
    similar = serializers.FloatField()
    genre = serializers.FloatField()
    mood = serializers.FloatField()


class CanvasGraphRagItemSerializer(serializers.Serializer):
    music_id = serializers.IntegerField()
    music_name = serializers.CharField(allow_blank=True)
    artist_name = serializers.CharField(allow_null=True, allow_blank=True)
    album_name = serializers.CharField(allow_null=True, allow_blank=True)
    audio_url = serializers.CharField(allow_null=True, allow_blank=True)
    image_large_square = serializers.CharField(allow_null=True, allow_blank=True)
    image_square = serializers.CharField(allow_null=True, allow_blank=True)
    album_image = serializers.CharField(allow_null=True, allow_blank=True)
    relevance_score = serializers.FloatField()
    visual_weight = serializers.FloatField()
    cluster = serializers.CharField(allow_null=True, allow_blank=True)
    matched_tags = CanvasGraphRagMatchedTagSerializer(many=True)
    score_breakdown = CanvasGraphRagScoreBreakdownSerializer()
    source_types = serializers.ListField(child=serializers.CharField())
    explanations = CanvasGraphRagExplanationSerializer(many=True)


class CanvasGraphRagSignalCoverageSerializer(serializers.Serializer):
    direct_tag = serializers.IntegerField()
    similar = serializers.IntegerField()
    artist_genre = serializers.IntegerField()
    mood = serializers.IntegerField()


class CanvasGraphRagMetaSerializer(serializers.Serializer):
    returned = serializers.IntegerField()
    data_state = serializers.CharField()
    message = serializers.CharField(required=False, allow_blank=True)
    total_candidates = serializers.IntegerField(required=False)
    graph_version = serializers.CharField(required=False)
    available_signals = serializers.ListField(
        child=serializers.CharField(), required=False
    )
    signal_coverage = CanvasGraphRagSignalCoverageSerializer(required=False)


class CanvasGraphRagResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    query = CanvasGraphRagQuerySerializer()
    items = CanvasGraphRagItemSerializer(many=True)
    meta = CanvasGraphRagMetaSerializer()


# ============================================================
# 캔버스 자연어 질의응답 (Canvas NLQ)
# ============================================================


class CanvasAskRequestSerializer(serializers.Serializer):
    """POST /api/v1/canvas/ask 요청 검증."""

    query = serializers.CharField(allow_blank=False, trim_whitespace=True)
    limit = serializers.IntegerField(required=False, allow_null=True)


class CanvasInterpretationSerializer(serializers.Serializer):
    """LLM 질의 해석 결과 (① 태그 추출)."""

    original_query = serializers.CharField(allow_blank=True)
    extracted_tags = serializers.ListField(child=serializers.CharField())
    source = serializers.ChoiceField(choices=["llm", "fallback_direct"])


class CanvasAskResponseSerializer(CanvasGraphRagResponseSerializer):
    """기존 CanvasGraphRagResponseSerializer 계약 + interpretation 필드."""

    interpretation = CanvasInterpretationSerializer()


class CanvasAnswerRequestSerializer(serializers.Serializer):
    """POST /api/v1/canvas/answer 요청 검증."""

    query = serializers.CharField(allow_blank=False, trim_whitespace=True)
    tags = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class CanvasAnswerResponseSerializer(serializers.Serializer):
    """POST /api/v1/canvas/answer 응답 (③ 답변 생성)."""

    answer = serializers.CharField(allow_null=True, required=False)
    model = serializers.CharField(required=False)
    reason = serializers.CharField(required=False)
