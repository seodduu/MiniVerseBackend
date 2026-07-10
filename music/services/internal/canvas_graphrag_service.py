"""Hybrid graph ranking for the Canvas music search."""

import math
from collections import defaultdict
from typing import Any, Dict, Iterable, List

from django.db.models import Q

from ...models import ArtistGenres, Music, MusicSimilar, MusicTags, Tags
from .mood_lexicon import MOOD_COORDS


class CanvasGraphRagService:
    """Search the relational music graph and return explainable ranking data."""

    DEFAULT_LIMIT = 120
    MAX_LIMIT = 150
    MAX_DIRECT_SEEDS = 150
    MAX_SIMILAR_PER_SEED = 30
    MAX_SIMILAR_CANDIDATES = 300
    MAX_GENRE_CANDIDATES = 300
    SIMILAR_DECAY = 0.75
    MOOD_RADIUS = 1.0
    WEIGHTS = {"direct_tag": 0.50, "similar": 0.25, "genre": 0.10, "mood": 0.15}

    @classmethod
    def search(cls, tag_values: List[str], limit: int | None = None) -> Dict[str, Any]:
        clean_tags = cls._normalize_tags(tag_values)
        safe_limit = cls._normalize_limit(limit)
        readiness = cls._check_graph_readiness()
        if readiness:
            return cls._empty_response(clean_tags, "empty_data", readiness)
        if not clean_tags:
            return cls._no_match_response([], [], [], "missing_query", "검색 태그가 필요합니다.")

        resolved_tags = list(
            Tags.objects.filter(tag_key__in=clean_tags, is_deleted=False).order_by("tag_id")
        )
        resolved_keys = {tag.tag_key for tag in resolved_tags}
        unresolved = [tag for tag in clean_tags if tag not in resolved_keys]
        if not resolved_tags:
            return cls._no_match_response(
                clean_tags,
                [],
                unresolved,
                "query_tags_not_found",
                "검색한 태그가 아직 등록되지 않았습니다.",
            )

        direct_edges = list(
            MusicTags.objects.filter(
                tag__in=resolved_tags,
                is_deleted=False,
                music__is_deleted=False,
                tag__is_deleted=False,
            )
            .select_related("music", "music__artist", "music__album", "tag")
            .order_by("-score", "music_id")[: cls.MAX_DIRECT_SEEDS * len(resolved_tags)]
        )
        candidates = cls._build_direct_candidates(direct_edges, len(resolved_tags))
        seed_ids = set(candidates)

        cls._expand_similar_candidates(candidates, seed_ids)
        cls._expand_genre_query_candidates(candidates, resolved_tags)
        if not candidates:
            return cls._no_results_response(clean_tags, resolved_tags, unresolved)

        cls._load_candidate_music(candidates)
        cls._attach_genre_scores(candidates, seed_ids, resolved_tags)
        cls._attach_mood_scores(candidates, resolved_tags)
        items = cls._rank_and_serialize(candidates, safe_limit)
        coverage = cls._signal_coverage(candidates)
        available = ["direct_tag"]
        if MusicSimilar.objects.exists():
            available.append("similar")
        if ArtistGenres.objects.exists():
            available.append("artist_genre")
        if any(tag.tag_key.casefold() in MOOD_COORDS for tag in resolved_tags):
            available.append("mood")

        return {
            "status": "ok",
            "query": cls._query_payload(clean_tags, resolved_tags, unresolved),
            "items": items,
            "meta": {
                "returned": len(items),
                "total_candidates": len(candidates),
                "data_state": "ready",
                "graph_version": "hybrid-graph-v2",
                "available_signals": available,
                "signal_coverage": coverage,
            },
        }

    @classmethod
    def _build_direct_candidates(cls, edges: Iterable[MusicTags], query_tag_count: int):
        candidates: Dict[int, Dict[str, Any]] = {}
        matched: Dict[int, Dict[str, float]] = defaultdict(dict)
        for edge in edges:
            music_id = edge.music_id
            score = cls._clamp(edge.score)
            key = edge.tag.tag_key
            matched[music_id][key] = max(matched[music_id].get(key, 0.0), score)
            candidates.setdefault(music_id, cls._candidate(edge.music))

        for music_id, candidate in candidates.items():
            ordered = sorted(matched[music_id].items(), key=lambda item: (-item[1], item[0]))
            candidate["matched_tags"] = [
                {"tag_key": key, "tag_name": key, "score": score} for key, score in ordered
            ]
            candidate["direct_tag_score"] = sum(score for _, score in ordered) / query_tag_count
            candidate["cluster"] = ordered[0][0] if ordered else None
            for key, score in ordered:
                candidate["explanations"].append(
                    cls._explanation(
                        "direct_tag",
                        [f"tag:{key}", f"music:{music_id}"],
                        score,
                        "검색 태그와 직접 연결된 곡입니다.",
                    )
                )
        return candidates

    @classmethod
    def _expand_similar_candidates(cls, candidates, seed_ids):
        if not seed_ids:
            return
        edges = MusicSimilar.objects.filter(
            Q(music_id__in=seed_ids) | Q(similar_music_id__in=seed_ids),
            is_deleted=False,
            music__is_deleted=False,
            similar_music__is_deleted=False,
        ).order_by("-match", "music_similar_id")
        per_seed = defaultdict(int)
        discovered = set()
        for edge in edges:
            connections = []
            if edge.music_id in seed_ids:
                connections.append((edge.music_id, edge.similar_music_id))
            if edge.similar_music_id in seed_ids:
                connections.append((edge.similar_music_id, edge.music_id))
            for seed_id, candidate_id in connections:
                if candidate_id in seed_ids or candidate_id == seed_id:
                    continue
                if per_seed[seed_id] >= cls.MAX_SIMILAR_PER_SEED:
                    continue
                if candidate_id not in discovered and len(discovered) >= cls.MAX_SIMILAR_CANDIDATES:
                    continue
                per_seed[seed_id] += 1
                discovered.add(candidate_id)
                seed = candidates[seed_id]
                path_score = seed["direct_tag_score"] * cls._clamp(edge.match) * cls.SIMILAR_DECAY
                candidate = candidates.setdefault(candidate_id, cls._candidate())
                if path_score > candidate["similar_score"]:
                    candidate["similar_score"] = path_score
                    candidate["cluster"] = seed["cluster"]
                    candidate["similar_explanation"] = cls._explanation(
                        "similar_track",
                        [f"tag:{seed['cluster']}", f"music:{seed_id}", f"music:{candidate_id}"],
                        path_score,
                        "검색 태그와 연결된 곡의 유사곡입니다.",
                    )

    @classmethod
    def _expand_genre_query_candidates(cls, candidates, resolved_tags):
        genre_names = [tag.tag_key for tag in resolved_tags if tag.tag_type == "genre"]
        if not genre_names:
            return
        query = Q()
        for name in genre_names:
            query |= Q(genre__genre_name__iexact=name.strip())
        artist_ids = list(
            ArtistGenres.objects.filter(
                query,
                is_deleted=False,
                artist__is_deleted=False,
                genre__is_deleted=False,
            ).values_list("artist_id", flat=True).distinct()
        )
        music_rows = Music.objects.filter(
            artist_id__in=artist_ids, is_deleted=False
        ).select_related("artist", "album")[: cls.MAX_GENRE_CANDIDATES]
        for music in music_rows:
            candidates.setdefault(music.music_id, cls._candidate(music))

    @classmethod
    def _load_candidate_music(cls, candidates):
        missing_ids = [music_id for music_id, data in candidates.items() if data["music"] is None]
        music_by_id = {
            music.music_id: music
            for music in Music.objects.filter(
                music_id__in=missing_ids, is_deleted=False
            ).select_related("artist", "album")
        }
        for music_id in list(candidates):
            if candidates[music_id]["music"] is None:
                music = music_by_id.get(music_id)
                if music is None:
                    del candidates[music_id]
                else:
                    candidates[music_id]["music"] = music

    @classmethod
    def _attach_genre_scores(cls, candidates, seed_ids, resolved_tags):
        artist_ids = {
            data["music"].artist_id for data in candidates.values() if data["music"].artist_id
        }
        if not artist_ids:
            return
        rows = ArtistGenres.objects.filter(
            artist_id__in=artist_ids,
            is_deleted=False,
            artist__is_deleted=False,
            genre__is_deleted=False,
        ).select_related("genre")
        genres_by_artist = defaultdict(dict)
        for row in rows:
            if row.genre.genre_name:
                genres_by_artist[row.artist_id][row.genre_id] = row.genre.genre_name.strip()

        context_weights = {}
        query_genres = {tag.tag_key.casefold() for tag in resolved_tags if tag.tag_type == "genre"}
        for seed_id in seed_ids:
            seed = candidates.get(seed_id)
            if not seed or not seed["music"].artist_id:
                continue
            for genre_id in genres_by_artist[seed["music"].artist_id]:
                context_weights[genre_id] = max(
                    context_weights.get(genre_id, 0.0), seed["direct_tag_score"]
                )
        for artist_genres in genres_by_artist.values():
            for genre_id, genre_name in artist_genres.items():
                if genre_name.casefold() in query_genres:
                    context_weights[genre_id] = max(context_weights.get(genre_id, 0.0), 1.0)
        denominator = sum(context_weights.values())
        if denominator <= 0:
            return
        for music_id, candidate in candidates.items():
            artist_id = candidate["music"].artist_id
            matches = [
                (genre_id, name)
                for genre_id, name in genres_by_artist.get(artist_id, {}).items()
                if genre_id in context_weights
            ]
            if not matches:
                continue
            candidate["genre_score"] = min(
                1.0, sum(context_weights[genre_id] for genre_id, _ in matches) / denominator
            )
            names = sorted({name for _, name in matches})
            candidate["explanations"].append(
                cls._explanation(
                    "artist_genre",
                    [f"genre:{name}" for name in names] + [f"music:{music_id}"],
                    candidate["genre_score"],
                    "검색 결과의 아티스트 장르 문맥과 연결된 곡입니다.",
                )
            )

    @classmethod
    def _attach_mood_scores(cls, candidates, resolved_tags):
        coords = [MOOD_COORDS[tag.tag_key.casefold()] for tag in resolved_tags if tag.tag_key.casefold() in MOOD_COORDS]
        if not coords:
            return
        query_v = sum(coord[0] for coord in coords) / len(coords)
        query_a = sum(coord[1] for coord in coords) / len(coords)
        for music_id, candidate in candidates.items():
            music = candidate["music"]
            if music.valence is None or music.arousal is None:
                continue
            valence, arousal = float(music.valence), float(music.arousal)
            if not (-1 <= valence <= 1 and -1 <= arousal <= 1):
                continue
            distance = math.hypot(valence - query_v, arousal - query_a)
            candidate["mood_score"] = max(0.0, 1.0 - distance / cls.MOOD_RADIUS)
            if candidate["mood_score"] > 0:
                candidate["explanations"].append(
                    cls._explanation(
                        "mood_proximity",
                        [f"mood:{query_v:.3f},{query_a:.3f}", f"music:{music_id}"],
                        candidate["mood_score"],
                        "검색 무드 좌표와 가까운 곡입니다.",
                    )
                )

    @classmethod
    def _rank_and_serialize(cls, candidates, limit):
        rows = []
        for candidate in candidates.values():
            music = candidate["music"]
            breakdown = {
                "direct_tag": candidate["direct_tag_score"],
                "similar": candidate["similar_score"],
                "genre": candidate["genre_score"],
                "mood": candidate["mood_score"],
            }
            relevance = sum(cls.WEIGHTS[key] * value for key, value in breakdown.items())
            explanations = list(candidate["explanations"])
            if candidate.get("similar_explanation"):
                explanations.append(candidate["similar_explanation"])
            source_types = [
                key for key, value in (
                    ("direct_tag", breakdown["direct_tag"]),
                    ("similar_track", breakdown["similar"]),
                    ("artist_genre", breakdown["genre"]),
                    ("mood_proximity", breakdown["mood"]),
                ) if value > 0
            ]
            album, artist = music.album, music.artist
            rows.append({
                "music_id": music.music_id,
                "music_name": music.music_name,
                "artist_name": artist.artist_name if artist else None,
                "album_name": album.album_name if album else None,
                "audio_url": music.audio_url,
                "image_large_square": album.image_large_square if album else None,
                "image_square": album.image_square if album else None,
                "album_image": album.album_image if album else None,
                "relevance_score": round(cls._clamp(relevance), 4),
                "visual_weight": round(math.sqrt(cls._clamp(relevance)), 4),
                "cluster": candidate["cluster"],
                "matched_tags": candidate["matched_tags"],
                "score_breakdown": {key: round(value, 4) for key, value in breakdown.items()},
                "source_types": source_types,
                "explanations": explanations,
            })
        rows.sort(key=lambda row: (
            -row["relevance_score"], -len(row["source_types"]),
            -row["score_breakdown"]["direct_tag"], -row["music_id"],
        ))
        return rows[:limit]

    @staticmethod
    def _candidate(music=None):
        return {
            "music": music, "direct_tag_score": 0.0, "similar_score": 0.0,
            "genre_score": 0.0, "mood_score": 0.0, "matched_tags": [],
            "cluster": None, "explanations": [],
        }

    @staticmethod
    def _explanation(kind, path, weight, reason):
        return {"type": kind, "path": path, "weight": round(weight, 4), "reason": reason}

    @staticmethod
    def _clamp(value):
        try:
            return max(0.0, min(float(value or 0.0), 1.0))
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _signal_coverage(cls, candidates):
        return {
            "direct_tag": sum(c["direct_tag_score"] > 0 for c in candidates.values()),
            "similar": sum(c["similar_score"] > 0 for c in candidates.values()),
            "artist_genre": sum(c["genre_score"] > 0 for c in candidates.values()),
            "mood": sum(c["mood_score"] > 0 for c in candidates.values()),
        }

    @staticmethod
    def _normalize_tags(tag_values):
        seen, normalized = set(), []
        for raw in tag_values:
            for part in str(raw).split(","):
                tag = part.strip().lstrip("#").strip()
                if tag and tag not in seen:
                    normalized.append(tag)
                    seen.add(tag)
        return normalized[:3]

    @classmethod
    def _normalize_limit(cls, limit):
        try:
            parsed = cls.DEFAULT_LIMIT if limit is None else int(limit)
        except (TypeError, ValueError):
            parsed = cls.DEFAULT_LIMIT
        return max(1, min(parsed, cls.MAX_LIMIT))

    @staticmethod
    def _check_graph_readiness():
        if not Music.objects.exists():
            return "missing_music"
        if not Tags.objects.exists():
            return "missing_tags"
        if not MusicTags.objects.exists():
            return "missing_music_tags"
        return None

    @staticmethod
    def _query_payload(tags, resolved_tags, unresolved):
        return {
            "tags": tags,
            "resolved_tags": [
                {"tag_id": tag.tag_id, "tag_key": tag.tag_key, "tag_name": tag.tag_key}
                for tag in resolved_tags
            ],
            "unresolved_tags": unresolved,
        }

    @classmethod
    def _empty_response(cls, tags, status, data_state):
        messages = {
            "missing_music": "GraphRAG를 위한 음악 데이터가 아직 없습니다.",
            "missing_tags": "GraphRAG를 위한 태그 데이터가 아직 없습니다.",
            "missing_music_tags": "GraphRAG를 위한 곡-태그 연결 데이터가 아직 없습니다.",
        }
        return {
            "status": status,
            "query": {"tags": tags, "resolved_tags": [], "unresolved_tags": tags},
            "items": [],
            "meta": {"returned": 0, "data_state": data_state, "message": messages[data_state]},
        }

    @classmethod
    def _no_match_response(cls, tags, resolved, unresolved, data_state, message):
        return {
            "status": "no_query_match",
            "query": cls._query_payload(tags, resolved, unresolved),
            "items": [],
            "meta": {"returned": 0, "data_state": data_state, "message": message},
        }

    @classmethod
    def _no_results_response(cls, tags, resolved, unresolved):
        return {
            "status": "no_results",
            "query": cls._query_payload(tags, resolved, unresolved),
            "items": [],
            "meta": {
                "returned": 0,
                "data_state": "no_connected_tracks",
                "message": "태그는 있지만 연결된 곡이 없습니다.",
            },
        }
