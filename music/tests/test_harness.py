def test_harness_runs():
    assert 1 + 1 == 2


import responses
import requests


@responses.activate
def test_responses_mock_works():
    responses.add(responses.GET, "https://example.test/x", json={"ok": True}, status=200)
    r = requests.get("https://example.test/x", timeout=3)
    assert r.json() == {"ok": True}
