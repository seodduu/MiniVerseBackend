import pytest
from unittest.mock import patch

TRACK = {
    "deezer_id": "dz_track_1", "music_name": "Super Shy",
    "artist_name": "NewJeans", "artist_deezer_id": "dz_artist_1",
    "artist_image": "https://cdn-images.dzcdn.net/images/artist/xl.jpg",
    "album_name": "Get Up", "album_deezer_id": "dz_album_1",
    "album_image": "https://cdn-images.dzcdn.net/images/cover/xl.jpg",
    "isrc": "KRA402400123", "release_date": "2023-07-21",
    "duration": 154, "preview_url": "https://cdns-preview.dzcdn.net/stream/preview.mp3",
    "deezer_url": "https://www.deezer.com/track/dz_track_1",
}


@pytest.mark.django_db
@patch("music.tasks.deezer_save.fetch_similar_tracks_task")
@patch("music.tasks.deezer_save.fetch_mood_tags_task")
def test_saves_track_with_fk_chain(mock_mood, mock_sim):
    from music.tasks.deezer_save import save_deezer_track_to_db_task
    from music.models import Music, Artists, Albums
    mid = save_deezer_track_to_db_task(TRACK)
    m = Music.objects.get(music_id=mid)
    assert m.deezer_id == "dz_track_1"
    assert m.audio_url == "https://cdns-preview.dzcdn.net/stream/preview.mp3"
    assert m.isrc == "KRA402400123"
    assert m.artist.deezer_id == "dz_artist_1"
    assert m.artist.artist_image == "https://cdn-images.dzcdn.net/images/artist/xl.jpg"
    assert m.artist.image_large_circle == "https://cdn-images.dzcdn.net/images/artist/xl.jpg"
    assert m.album.deezer_id == "dz_album_1"
    assert str(m.album.release_date) == "2023-07-21"
    assert m.album.album_image == "https://cdn-images.dzcdn.net/images/cover/xl.jpg"
    mock_mood.delay.assert_called_once_with(m.music_id, "NewJeans", "Super Shy")
    mock_sim.delay.assert_called_once_with(m.music_id, "NewJeans", "Super Shy")


@pytest.mark.django_db
@patch("music.tasks.deezer_save.fetch_similar_tracks_task")
@patch("music.tasks.deezer_save.fetch_mood_tags_task")
def test_dedup_by_deezer_id(mock_mood, mock_sim):
    from music.tasks.deezer_save import save_deezer_track_to_db_task
    from music.models import Music
    first = save_deezer_track_to_db_task(TRACK)
    second = save_deezer_track_to_db_task(TRACK)
    assert first == second
    assert Music.objects.filter(deezer_id="dz_track_1").count() == 1
