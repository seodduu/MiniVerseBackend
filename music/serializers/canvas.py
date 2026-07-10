"""
/canvas GraphRAG 응답 Serializers.
"""
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
    type = serializers.CharField(allow_blank=True)
    path = serializers.ListField(child=serializers.CharField())
    weight = serializers.FloatField()
    reason = serializers.CharField(allow_blank=True)


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
    explanations = CanvasGraphRagExplanationSerializer(many=True)


class CanvasGraphRagMetaSerializer(serializers.Serializer):
    returned = serializers.IntegerField()
    data_state = serializers.CharField(allow_blank=True)
    message = serializers.CharField(required=False, allow_blank=True)
    total_candidates = serializers.IntegerField(required=False)
    graph_version = serializers.CharField(required=False, allow_blank=True)


class CanvasGraphRagResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    query = CanvasGraphRagQuerySerializer()
    items = CanvasGraphRagItemSerializer(many=True)
    meta = CanvasGraphRagMetaSerializer()
