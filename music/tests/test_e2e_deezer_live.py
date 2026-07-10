"""실제 Deezer API를 호출하는 E2E 검증 (네트워크 필요, mock 아님)."""
import pytest
from unittest.mock import patch


@pytest.mark.django_db
@patch("music.tasks.deezer_save.fetch_similar_tracks_task")
@patch("music.tasks.deezer_save.fetch_mood_tags_task")
def test_real_deezer_search_and_save(mock_mood, mock_sim):
    from music.services.external.deezer import DeezerService
    from music.tasks.deezer_save import save_deezer_track_to_db_task
    from music.models import Music

    # 1) 실제 Deezer 검색
    tracks = DeezerService.search_tracks("Dua Lipa Levitating", limit=1)
    assert tracks, "Deezer가 결과를 주지 않음"
    t = tracks[0]
    print("\n[실제 Deezer 검색]", t["music_name"], "/", t["artist_name"])

    # 2) 실제 저장 파이프라인 실행
    mid = save_deezer_track_to_db_task(t)
    assert mid is not None

    # 3) DB에 실제 데이터가 들어갔는지
    m = Music.objects.get(music_id=mid)
    print("[저장됨] deezer_id:", m.deezer_id, "isrc:", m.isrc)
    print("[미리듣기] audio_url:", m.audio_url[:60])
    print("[앨범커버] :", m.album.album_image[:60])
    print("[아티스트이미지]:", m.artist.artist_image[:60])
    print("[재생시간]:", m.duration, "초")
    assert m.audio_url.startswith("http")       # 실제 preview URL
    assert m.album.album_image.startswith("http")  # 실제 커버
    assert m.artist.artist_image.startswith("http")  # 실제 아티스트 이미지

    # 4) 중복 저장 방지 (같은 곡 재저장 시 같은 id)
    assert save_deezer_track_to_db_task(t) == mid
    assert Music.objects.filter(deezer_id=t["deezer_id"]).count() == 1
    print("[중복방지] OK")
