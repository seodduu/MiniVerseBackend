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
        # 오디오 blob은 completed 단계에서만 존재가 보장되므로,
        # preparing_audio 단계에서 URL을 노출하면 404로 이어질 수 있다.
        if obj.music_id and obj.phase == GenerationJob.PHASE_COMPLETED:
            return f"/api/v1/{obj.music_id}/audio/"
        return None
