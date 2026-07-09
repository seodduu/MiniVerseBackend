from music.services.internal.mood_lexicon import derive_valence_arousal, MOOD_COORDS


def test_single_tag_returns_its_coords():
    v, a = derive_valence_arousal([("happy", 1.0)])
    assert (v, a) == MOOD_COORDS["happy"]


def test_weighted_average_of_two_tags():
    # happy(+0.8,+0.6) score 1.0, sad(-0.7,-0.4) score 1.0 → 평균 (0.05, 0.1)
    v, a = derive_valence_arousal([("happy", 1.0), ("sad", 1.0)])
    assert round(v, 3) == round((0.8 + -0.7) / 2, 3)
    assert round(a, 3) == round((0.6 + -0.4) / 2, 3)


def test_no_known_tags_returns_none():
    assert derive_valence_arousal([("unknown_xyz", 1.0)]) == (None, None)


def test_empty_returns_none():
    assert derive_valence_arousal([]) == (None, None)
