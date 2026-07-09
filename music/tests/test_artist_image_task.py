import pytest
from unittest.mock import patch


@pytest.mark.django_db
@patch("music.tasks.metadata.SpotifyService.get_artist",
       return_value={"artist_image": "https://i.scdn.co/artist/640",
                     "genres": ["k-pop", "dance pop"], "spotify_url": ""})
def test_artist_image_and_genre_nodes(mock_get):
    from music.tasks.metadata import fetch_artist_image_task
    from music.models import Artists, Genres, ArtistGenres
    a = Artists.objects.create(artist_name="NewJeans", spotify_id="sp_artist_1",
                               artist_image="", is_deleted=False)
    fetch_artist_image_task(a.artist_id, "sp_artist_1", "NewJeans")
    a.refresh_from_db()
    assert a.artist_image == "https://i.scdn.co/artist/640"
    assert a.image_large_circle == "https://i.scdn.co/artist/640"
    genre_keys = set(Genres.objects.values_list("genre_name", flat=True))
    assert {"k-pop", "dance pop"}.issubset(genre_keys)
    assert ArtistGenres.objects.filter(artist=a).count() == 2
