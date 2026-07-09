from django.db import models


class GenerationJob(models.Model):
    """AI 음악 생성 작업의 진행 상태를 서버 측에서 추적하는 레코드."""

    PHASE_GENERATING = 'generating'
    PHASE_PREPARING = 'preparing_audio'
    PHASE_COMPLETED = 'completed'
    PHASE_FAILED = 'failed'
    PHASE_CHOICES = [
        (PHASE_GENERATING, 'Generating'),
        (PHASE_PREPARING, 'Preparing audio'),
        (PHASE_COMPLETED, 'Completed'),
        (PHASE_FAILED, 'Failed'),
    ]
    ACTIVE_PHASES = [PHASE_GENERATING, PHASE_PREPARING]

    job_id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey('Users', models.DO_NOTHING, db_index=True)
    celery_task_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    phase = models.CharField(max_length=32, choices=PHASE_CHOICES, default=PHASE_GENERATING)
    original_prompt = models.CharField(max_length=1500)
    converted_prompt = models.CharField(max_length=2000, blank=True, null=True)
    music = models.ForeignKey('Music', models.SET_NULL, blank=True, null=True)
    error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'ai_generation_job'
        indexes = [models.Index(fields=['user', 'phase'])]
        verbose_name = 'AI 생성 작업'
        verbose_name_plural = '5️⃣ 🤖 AI - 생성 작업'


class MusicAudioBlob(models.Model):
    """Postgres에 오디오 바이너리를 저장하는 곡당 1행 테이블 (S3 대체)."""

    music = models.OneToOneField('Music', models.CASCADE, primary_key=True)
    content_type = models.CharField(max_length=100, default='audio/mpeg')
    data = models.BinaryField()
    size = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'music_audio_blob'
        verbose_name = '오디오 블롭'
        verbose_name_plural = '2️⃣ 🎵 MUSIC - 오디오 블롭'
