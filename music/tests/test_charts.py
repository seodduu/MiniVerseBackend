from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from music.models import Albums, Artists, Music
from music.views.charts import ChartView


@pytest.mark.django_db
def test_realtime_chart_uses_music_dummy_data_when_snapshot_is_missing():
    artist = Artists.objects.create(artist_name="Dummy Artist", is_deleted=False)
    album = Albums.objects.create(
        artist=artist,
        album_name="Dummy Album",
        is_deleted=False,
    )
    newest = Music.objects.create(
        music_name="Newest Dummy Track",
        artist=artist,
        album=album,
        genre="Pop",
        duration=180,
        is_ai=False,
        audio_url="https://example.test/newest.mp3",
        is_deleted=False,
    )
    older = Music.objects.create(
        music_name="Older Dummy Track",
        artist=artist,
        album=album,
        genre="Rock",
        duration=210,
        is_ai=True,
        audio_url="https://example.test/older.mp3",
        is_deleted=False,
    )
    Music.objects.filter(music_id=newest.music_id).update(updated_at=timezone.now())
    Music.objects.filter(music_id=older.music_id).update(
        updated_at=timezone.now() + timedelta(minutes=1)
    )

    request = APIRequestFactory().get("/api/v1/charts/realtime")
    response = ChartView.as_view()(request, type="realtime")

    assert response.status_code == 200
    assert response.data["type"] == "realtime"
    assert response.data["total_count"] == 2
    assert [item["rank"] for item in response.data["items"]] == [1, 2]
    assert [item["music"]["music_id"] for item in response.data["items"]] == [
        older.music_id,
        newest.music_id,
    ]
    assert [item["play_count"] for item in response.data["items"]] == [2, 1]


@pytest.mark.django_db
def test_non_realtime_chart_still_returns_404_when_snapshot_is_missing():
    request = APIRequestFactory().get("/api/v1/charts/daily")
    response = ChartView.as_view()(request, type="daily")

    assert response.status_code == 404
