"""실제 Last.fm API를 호출하는 무드 태그/유사곡 E2E (네트워크 필요, mock 아님)."""
import pytest


@pytest.mark.django_db
def test_real_lastfm_mood_tags():
    from music.tasks.enrichment import fetch_mood_tags_task
    from music.models import Music, Artists, MusicTags
    artist = Artists.objects.create(artist_name="Bon Iver", is_deleted=False)
    m = Music.objects.create(music_name="Skinny Love", artist=artist, is_deleted=False)

    fetch_mood_tags_task(m.music_id, "Bon Iver", "Skinny Love")  # 실제 Last.fm

    edges = {mt.tag.tag_key: round(mt.score, 3) for mt in MusicTags.objects.filter(music=m)}
    print("\n[실제 무드 태그]", edges)
    m.refresh_from_db()
    print("[역산된 좌표] valence:", m.valence, "arousal:", m.arousal)
    assert edges, "무드 태그가 하나도 안 생김"
    assert m.valence is not None and m.arousal is not None


@pytest.mark.django_db
def test_real_lastfm_similar_edges():
    from music.services.external.lastfm import LastfmService
    from music.tasks.enrichment import fetch_similar_tracks_task
    from music.models import Music, Artists, MusicSimilar

    # 실제 유사곡 목록 조회
    similar = LastfmService.get_track_similar("Dua Lipa", "Levitating")
    assert similar, "유사곡이 안 나옴"
    print("\n[실제 유사곡 상위3]", [(a, t, round(mm, 2)) for a, t, mm in similar[:3]])

    dua = Artists.objects.create(artist_name="Dua Lipa", is_deleted=False)
    src = Music.objects.create(music_name="Levitating", artist=dua, is_deleted=False)
    # 상위 2개 유사곡을 DB에 미리 생성 (그래야 링크됨)
    for a_name, t_name, _ in similar[:2]:
        art, _ = Artists.objects.get_or_create(artist_name=a_name, defaults={"is_deleted": False})
        Music.objects.create(music_name=t_name, artist=art, is_deleted=False)

    fetch_similar_tracks_task(src.music_id, "Dua Lipa", "Levitating")  # 실제 Last.fm

    links = [(l.similar_music.music_name, round(l.match, 3)) for l in MusicSimilar.objects.filter(music=src)]
    print("[생성된 유사 엣지]", links)
    assert len(links) >= 1
