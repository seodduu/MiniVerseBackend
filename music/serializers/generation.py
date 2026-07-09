from rest_framework import serializers

from ..models import GenerationJob


class GenerationJobSerializer(serializers.ModelSerializer):
    music_id = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()

    class Meta:
        model = GenerationJob
        fields = [
            'job_id', 'phase', 'music_id', 'audio_url',
            'original_prompt', 'converted_prompt', 'error',
        ]

    def get_music_id(self, obj):
        return obj.music_id  # FK id, music 없으면 None

    def get_audio_url(self, obj):
        if obj.music_id:
            return f"/api/v1/tracks/{obj.music_id}/audio/"
        return None
