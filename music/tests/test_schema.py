import pytest
from django.db import connection


@pytest.mark.django_db
def test_music_tags_allows_multiple_tags_per_track():
    from music.models import Music, Tags, MusicTags
    m = Music.objects.create(music_name="T", is_deleted=False)
    t1 = Tags.objects.create(tag_key="happy", tag_type="mood", is_deleted=False)
    t2 = Tags.objects.create(tag_key="upbeat", tag_type="mood", is_deleted=False)
    MusicTags.objects.create(music=m, tag=t1, score=0.9, is_deleted=False)
    MusicTags.objects.create(music=m, tag=t2, score=0.7, is_deleted=False)
    assert MusicTags.objects.filter(music=m).count() == 2


@pytest.mark.django_db
def test_new_columns_exist():
    cols = {c.name for c in connection.introspection.get_table_description(
        connection.cursor(), 'music')}
    assert 'deezer_id' in cols and 'isrc' in cols and 'lyrics' not in cols
