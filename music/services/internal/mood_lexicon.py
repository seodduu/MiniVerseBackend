"""
무드 태그 → (valence, arousal) 좌표 사전 및 역산 유틸.
Russell circumplex 근사. valence: 긍정도(-1~+1), arousal: 활기(-1~+1).
"""
from typing import List, Optional, Tuple

MOOD_COORDS = {
    "happy": (0.8, 0.6),
    "upbeat": (0.5, 0.8),
    "positive": (0.7, 0.3),
    "uplifting": (0.7, 0.5),
    "feel good": (0.7, 0.4),
    "energetic": (0.0, 0.9),
    "party": (0.6, 0.8),
    "chill": (0.3, -0.6),
    "mellow": (0.2, -0.5),
    "calm": (0.3, -0.7),
    "dreamy": (0.2, -0.3),
    "romantic": (0.5, -0.2),
    "melancholic": (-0.6, -0.3),
    "sad": (-0.7, -0.4),
    "dark": (-0.6, 0.2),
}


def derive_valence_arousal(
    scored_tags: List[Tuple[str, float]]
) -> Tuple[Optional[float], Optional[float]]:
    total_w = 0.0
    v_sum = 0.0
    a_sum = 0.0
    for key, score in scored_tags:
        coord = MOOD_COORDS.get(key)
        if coord is None:
            continue
        w = max(float(score), 0.0)
        if w == 0.0:
            w = 1.0  # score가 0이어도 태그 존재는 반영
        v_sum += coord[0] * w
        a_sum += coord[1] * w
        total_w += w
    if total_w == 0.0:
        return (None, None)
    return (v_sum / total_w, a_sum / total_w)
