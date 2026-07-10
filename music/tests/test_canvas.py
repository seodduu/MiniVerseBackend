from django.test import TestCase
from rest_framework.test import APIClient

from music.models import (
    Albums,
    ArtistGenres,
    Artists,
    Genres,
    Music,
    MusicSimilar,
    MusicTags,
    Tags,
)


class CanvasGraphRagTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def artist(self, name):
        return Artists.objects.create(artist_name=name)

    def music(self, name, artist, **kwargs):
        album = Albums.objects.create(artist=artist, album_name=f"{name} album")
        return Music.objects.create(
            artist=artist,
            album=album,
            music_name=name,
            audio_url=f"https://example.com/{name}.mp3",
            **kwargs,
        )

    def tag(self, key, tag_type="mood"):
        return Tags.objects.create(tag_key=key, tag_type=tag_type)

    def search(self, tags, **params):
        return self.client.get("/api/v1/canvas/graphrag", {"tags": tags, **params})

    def test_empty_database_returns_explicit_data_state(self):
        response = self.search("happy")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "empty_data")
        self.assertEqual(response.json()["meta"]["data_state"], "missing_music")

    def test_direct_score_uses_query_coverage_and_absolute_fusion(self):
        artist = self.artist("direct artist")
        full = self.music("full", artist, valence=0.65, arousal=0.7)
        partial = self.music("partial", artist)
        happy, upbeat = self.tag("happy"), self.tag("upbeat")
        MusicTags.objects.create(music=full, tag=happy, score=0.8)
        MusicTags.objects.create(music=full, tag=upbeat, score=0.6)
        MusicTags.objects.create(music=partial, tag=happy, score=1.0)

        data = self.search("happy,upbeat").json()
        items = {item["music_id"]: item for item in data["items"]}

        self.assertEqual(data["meta"]["graph_version"], "hybrid-graph-v2")
        self.assertAlmostEqual(items[full.music_id]["score_breakdown"]["direct_tag"], 0.7)
        self.assertAlmostEqual(items[partial.music_id]["score_breakdown"]["direct_tag"], 0.5)
        self.assertGreater(items[full.music_id]["relevance_score"], items[partial.music_id]["relevance_score"])
        self.assertIn("mood_proximity", items[full.music_id]["source_types"])

    def test_similar_expansion_reads_outgoing_and_incoming_edges(self):
        artist = self.artist("similar artist")
        seed = self.music("seed", artist)
        outgoing = self.music("outgoing", artist)
        incoming = self.music("incoming", artist)
        happy = self.tag("happy")
        MusicTags.objects.create(music=seed, tag=happy, score=0.8)
        MusicSimilar.objects.create(music=seed, similar_music=outgoing, match=0.9)
        MusicSimilar.objects.create(music=incoming, similar_music=seed, match=0.7)

        data = self.search("happy").json()
        items = {item["music_id"]: item for item in data["items"]}

        self.assertAlmostEqual(items[outgoing.music_id]["score_breakdown"]["similar"], 0.54)
        self.assertAlmostEqual(items[incoming.music_id]["score_breakdown"]["similar"], 0.42)
        self.assertEqual(items[outgoing.music_id]["cluster"], "happy")
        self.assertIn("similar_track", items[outgoing.music_id]["source_types"])

    def test_artist_genre_scores_context_and_expands_genre_query(self):
        seed_artist = self.artist("seed artist")
        same_genre_artist = self.artist("same genre artist")
        seed = self.music("genre seed", seed_artist)
        genre_candidate = self.music("genre candidate", same_genre_artist)
        rock = Genres.objects.create(genre_name="rock")
        ArtistGenres.objects.create(artist=seed_artist, genre=rock)
        ArtistGenres.objects.create(artist=same_genre_artist, genre=rock)
        happy = self.tag("happy")
        rock_tag = self.tag("rock", tag_type="genre")
        MusicTags.objects.create(music=seed, tag=happy, score=0.9)

        context_data = self.search("happy").json()
        context_item = next(item for item in context_data["items"] if item["music_id"] == seed.music_id)
        self.assertEqual(context_item["score_breakdown"]["genre"], 1.0)

        genre_data = self.search(rock_tag.tag_key).json()
        genre_items = {item["music_id"]: item for item in genre_data["items"]}
        self.assertIn(genre_candidate.music_id, genre_items)
        self.assertEqual(genre_items[genre_candidate.music_id]["score_breakdown"]["genre"], 1.0)
        self.assertIn("artist_genre", genre_items[genre_candidate.music_id]["source_types"])

    def test_missing_optional_signals_do_not_block_direct_results(self):
        artist = self.artist("minimal artist")
        track = self.music("minimal", artist)
        unknown = self.tag("not-in-mood-lexicon")
        MusicTags.objects.create(music=track, tag=unknown, score=0.6)

        data = self.search(unknown.tag_key, limit=1).json()
        item = data["items"][0]

        self.assertEqual(data["status"], "ok")
        self.assertEqual(item["music_id"], track.music_id)
        self.assertEqual(item["score_breakdown"], {
            "direct_tag": 0.6,
            "similar": 0.0,
            "genre": 0.0,
            "mood": 0.0,
        })
        self.assertEqual(item["relevance_score"], 0.3)
