from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('music', '0002_generationjob_musicaudioblob'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='generationjob',
            constraint=models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(phase__in=['generating', 'preparing_audio']),
                name='uniq_active_generation_per_user',
            ),
        ),
    ]
