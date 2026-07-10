import pytest
from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch


@pytest.mark.django_db
@patch("music.tasks.refresh.fetch_similar_tracks_task")
@patch("music.tasks.refresh.fetch_mood_tags_task")
def test_refresh_retriggers_only_stale(mock_mood, mock_sim):
    from music.tasks.refresh import refresh_stale_music_task
    from music.models import Music
    old = Music.objects.create(music_name="Old", is_deleted=False)
    Music.all_objects.filter(pk=old.pk).update(
        updated_at=timezone.now() - timedelta(days=40))
    Music.objects.create(music_name="Fresh", is_deleted=False)  # 최근
    refresh_stale_music_task()
    assert mock_mood.delay.call_count == 1
