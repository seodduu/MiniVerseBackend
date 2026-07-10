from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('music', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='GenerationJob',
            fields=[
                ('job_id', models.BigAutoField(primary_key=True, serialize=False)),
                ('celery_task_id', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('phase', models.CharField(choices=[('generating', 'Generating'), ('preparing_audio', 'Preparing audio'), ('completed', 'Completed'), ('failed', 'Failed')], default='generating', max_length=32)),
                ('original_prompt', models.CharField(max_length=1500)),
                ('converted_prompt', models.CharField(blank=True, max_length=2000, null=True)),
                ('error', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('music', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='music.music')),
                ('user', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.DO_NOTHING, to='music.users')),
            ],
            options={
                'verbose_name': 'AI 생성 작업',
                'verbose_name_plural': '5️⃣ 🤖 AI - 생성 작업',
                'db_table': 'ai_generation_job',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='MusicAudioBlob',
            fields=[
                ('music', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='music.music')),
                ('content_type', models.CharField(default='audio/mpeg', max_length=100)),
                ('data', models.BinaryField()),
                ('size', models.BigIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': '오디오 블롭',
                'verbose_name_plural': '2️⃣ 🎵 MUSIC - 오디오 블롭',
                'db_table': 'music_audio_blob',
                'managed': True,
            },
        ),
        migrations.AddIndex(
            model_name='generationjob',
            index=models.Index(fields=['user', 'phase'], name='ai_gen_job_user_phase_idx'),
        ),
    ]
