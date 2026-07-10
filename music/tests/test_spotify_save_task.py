import pytest
from unittest.mock import patch

TRACK = {
    "spotify_id": "sp_track_1", "music_name": "Super Shy",
    "artist_name": "NewJeans", "artist_spotify_id": "sp_artist_1",
    "album_name": "Get Up", "album_spotify_id": "sp_album_1",
    "album_image_640": "https://i.scdn.co/image/640",
    "album_image_300": "https://i.scdn.co/image/300",
    "album_image_64": "https://i.scdn.co/image/64",
    "isrc": "KRA402400123", "release_date": "2023-07-21",
    "duration": 154, "spotify_url": "https://open.spotify.com/track/sp_track_1",
}


@pytest.mark.django_db
@patch("music.tasks.spotify_save.fetch_similar_tracks_task")
@patch("music.tasks.spotify_save.fetch_mood_tags_task")
@patch("music.tasks.spotify_save.fetch_artist_image_task")
@patch("music.tasks.spotify_save.iTunesService.search_preview", return_value="https://prev.m4a")
def test_saves_track_with_fk_chain(mock_prev, mock_img, mock_mood, mock_sim):
    from music.tasks.spotify_save import save_spotify_track_to_db_task
    from music.models import Music, Artists, Albums
    mid = save_spotify_track_to_db_task(TRACK)
    m = Music.objects.get(music_id=mid)
    assert m.spotify_id == "sp_track_1"
    assert m.audio_url == "https://prev.m4a"
    assert m.isrc == "KRA402400123"
    assert m.artist.spotify_id == "sp_artist_1"
    assert m.album.spotify_id == "sp_album_1"
    assert str(m.album.release_date) == "2023-07-21"
    assert m.album.album_image == "https://i.scdn.co/image/640"


@pytest.mark.django_db
@patch("music.tasks.spotify_save.fetch_similar_tracks_task")
@patch("music.tasks.spotify_save.fetch_mood_tags_task")
@patch("music.tasks.spotify_save.fetch_artist_image_task")
@patch("music.tasks.spotify_save.iTunesService.search_preview", return_value="")
def test_dedup_by_spotify_id(mock_prev, mock_img, mock_mood, mock_sim):
    from music.tasks.spotify_save import save_spotify_track_to_db_task
    from music.models import Music
    first = save_spotify_track_to_db_task(TRACK)
    second = save_spotify_track_to_db_task(TRACK)
    assert first == second
    assert Music.objects.filter(spotify_id="sp_track_1").count() == 1
