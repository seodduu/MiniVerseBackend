import pytest
from unittest.mock import patch


@pytest.mark.django_db
@patch("music.tasks.enrichment.LastfmService.get_track_top_tags",
       return_value=[("happy", 100), ("upbeat", 40)])
def test_mood_tags_creates_edges_and_coords(mock_tags):
    from music.tasks.enrichment import fetch_mood_tags_task
    from music.models import Music, MusicTags
    m = Music.objects.create(music_name="Super Shy", is_deleted=False)
    fetch_mood_tags_task(m.music_id, "NewJeans", "Super Shy")
    edges = {mt.tag.tag_key: mt.score for mt in MusicTags.objects.filter(music=m)}
    assert edges == {"happy": 1.0, "upbeat": 0.4}
    m.refresh_from_db()
    assert m.valence is not None and m.arousal is not None


@pytest.mark.django_db
@patch("music.tasks.enrichment.LastfmService.get_track_top_tags", return_value=[])
def test_mood_tags_no_tags_leaves_coords_null(mock_tags):
    from music.tasks.enrichment import fetch_mood_tags_task
    from music.models import Music, MusicTags
    m = Music.objects.create(music_name="X", is_deleted=False)
    fetch_mood_tags_task(m.music_id, "A", "X")
    assert MusicTags.objects.filter(music=m).count() == 0
    m.refresh_from_db()
    assert m.valence is None and m.arousal is None


@pytest.mark.django_db
@patch("music.tasks.enrichment.LastfmService.get_track_similar",
       return_value=[("IVE", "I AM", 1.0), ("aespa", "Spicy", 0.87)])
def test_similar_only_links_existing_tracks(mock_sim):
    from music.tasks.enrichment import fetch_similar_tracks_task
    from music.models import Music, Artists, MusicSimilar
    ive = Artists.objects.create(artist_name="IVE", is_deleted=False)
    src = Music.objects.create(music_name="Super Shy", is_deleted=False)
    # "I AM"은 DB에 존재, "Spicy"는 없음
    Music.objects.create(music_name="I AM", artist=ive, is_deleted=False)
    fetch_similar_tracks_task(src.music_id, "NewJeans", "Super Shy")
    links = MusicSimilar.objects.filter(music=src)
    assert links.count() == 1
    assert links.first().similar_music.music_name == "I AM"
