"""캔버스 자연어 질의응답(/canvas/ask, /canvas/answer) 테스트.

LLM 호출은 CanvasNlqService.extract_tags/generate_answer를 mock으로 대체해
파싱·폴백·계약을 검증한다 (실 Ollama 호출 없이 CI 안전).
"""

from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from music.models import Albums, Artists, Music, MusicTags, Tags


class CanvasNlqTestBase(TestCase):
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

    def seed_basic_graph(self):
        artist = self.artist("test artist")
        track = self.music("test track", artist)
        happy = self.tag("happy")
        MusicTags.objects.create(music=track, tag=happy, score=0.8)
        return artist, track, happy

    def ask(self, query, limit=None):
        payload = {"query": query}
        if limit is not None:
            payload["limit"] = limit
        return self.client.post("/api/v1/canvas/ask", payload, format="json")

    def answer(self, query, tags):
        return self.client.post(
            "/api/v1/canvas/answer", {"query": query, "tags": tags}, format="json"
        )


class CanvasAskLlmSuccessTest(CanvasNlqTestBase):
    @patch("music.views.canvas.CanvasNlqService.extract_tags")
    def test_llm_success_returns_llm_source_and_items(self, mock_extract):
        self.seed_basic_graph()
        mock_extract.return_value = (["happy"], "llm")

        response = self.ask("행복한 노래 틀어줘")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["interpretation"]["source"], "llm")
        self.assertEqual(data["interpretation"]["extracted_tags"], ["happy"])
        self.assertEqual(data["interpretation"]["original_query"], "행복한 노래 틀어줘")
        self.assertGreaterEqual(len(data["items"]), 1)


class CanvasAskFallbackTest(CanvasNlqTestBase):
    @patch("music.views.canvas.CanvasNlqService.extract_tags")
    def test_llm_failure_falls_back_to_exact_match(self, mock_extract):
        self.seed_basic_graph()
        mock_extract.return_value = (["happy"], "fallback_direct")

        response = self.ask("happy")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["interpretation"]["source"], "fallback_direct")
        self.assertEqual(data["interpretation"]["extracted_tags"], ["happy"])
        self.assertEqual(data["status"], "ok")

    @patch("music.views.canvas.CanvasNlqService.extract_tags")
    def test_fallback_with_zero_matches_returns_no_match_with_empty_tags(self, mock_extract):
        self.seed_basic_graph()
        mock_extract.return_value = ([], "fallback_direct")

        response = self.ask("asdf asdf 아무말")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["interpretation"]["source"], "fallback_direct")
        self.assertEqual(data["interpretation"]["extracted_tags"], [])
        # 기존 서비스 로직의 missing_query 계열이 그대로 노출되어야 한다.
        self.assertEqual(data["status"], "no_query_match")
        self.assertEqual(data["meta"]["data_state"], "missing_query")


class CanvasAnswerTest(CanvasNlqTestBase):
    @patch("music.views.canvas.CanvasNlqService.generate_answer")
    def test_answer_success_returns_answer_field(self, mock_generate):
        self.seed_basic_graph()
        mock_generate.return_value = "행복한 무드의 곡을 찾아드렸어요. 'test track'을 들어보세요."

        response = self.answer("행복한 노래 틀어줘", ["happy"])

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("test track", data["answer"])
        mock_generate.assert_called_once()

    def test_answer_no_results_returns_reason(self):
        # 태그가 어휘에 없거나 그래프가 비어 있어 검색 결과가 0곡인 경우.
        response = self.answer("아무 노래", ["nonexistent-tag"])

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["answer"])
        self.assertEqual(data["reason"], "no_results")

    @patch("music.views.canvas.CanvasNlqService.generate_answer")
    def test_answer_llm_unavailable_returns_reason(self, mock_generate):
        self.seed_basic_graph()
        mock_generate.return_value = None

        response = self.answer("행복한 노래 틀어줘", ["happy"])

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["answer"])
        self.assertEqual(data["reason"], "llm_unavailable")


class CanvasNlqServiceUnitTest(TestCase):
    """CanvasNlqService의 파싱/폴백 로직 단위 테스트 (requests.post mock)."""

    def setUp(self):
        Tags.objects.create(tag_key="happy", tag_type="mood")
        Tags.objects.create(tag_key="chill", tag_type="mood")

    @patch("music.services.internal.canvas_nlq_service.requests.post")
    def test_extract_tags_parses_valid_json_array(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {
            "message": {"content": '["happy", "chill"]'}
        }

        from music.services.internal.canvas_nlq_service import CanvasNlqService

        tags, source = CanvasNlqService.extract_tags("행복하고 편안한 노래")

        self.assertEqual(source, "llm")
        self.assertEqual(tags, ["happy", "chill"])

    @patch("music.services.internal.canvas_nlq_service.requests.post")
    def test_extract_tags_drops_out_of_vocabulary_tags(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {
            "message": {"content": '["happy", "not-a-real-tag"]'}
        }

        from music.services.internal.canvas_nlq_service import CanvasNlqService

        tags, source = CanvasNlqService.extract_tags("행복한 노래")

        self.assertEqual(source, "llm")
        self.assertEqual(tags, ["happy"])

    @patch("music.services.internal.canvas_nlq_service.requests.post")
    def test_extract_tags_falls_back_on_request_exception(self, mock_post):
        import requests

        mock_post.side_effect = requests.exceptions.Timeout("timeout")

        from music.services.internal.canvas_nlq_service import CanvasNlqService

        tags, source = CanvasNlqService.extract_tags("happy, chill")

        self.assertEqual(source, "fallback_direct")
        self.assertEqual(tags, ["happy", "chill"])

    @patch("music.services.internal.canvas_nlq_service.requests.post")
    def test_extract_tags_falls_back_when_all_tags_out_of_vocabulary(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {
            "message": {"content": '["not-a-real-tag"]'}
        }

        from music.services.internal.canvas_nlq_service import CanvasNlqService

        tags, source = CanvasNlqService.extract_tags("asdf asdf")

        self.assertEqual(source, "fallback_direct")
        self.assertEqual(tags, [])

    @patch("music.services.internal.canvas_nlq_service.requests.post")
    def test_generate_answer_returns_none_on_timeout(self, mock_post):
        import requests

        mock_post.side_effect = requests.exceptions.Timeout("timeout")

        from music.services.internal.canvas_nlq_service import CanvasNlqService

        answer = CanvasNlqService.generate_answer("query", ["happy"], [])

        self.assertIsNone(answer)
