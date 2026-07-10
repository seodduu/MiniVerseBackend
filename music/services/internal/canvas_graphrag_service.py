"""
/canvas GraphRAG 1차 검색 서비스.

현재 구현은 music_tags의 직접 태그 연결 점수를 GraphRAG relevance로 사용한다.
향후 music_similar, artist_genres, valence/arousal 점수를 이 서비스 안에서 확장한다.
"""
import math
from collections import defaultdict
from typing import Any, Dict, List

from ...models import Music, MusicTags, Tags


class CanvasGraphRagService:
    """캔버스용 GraphRAG 검색 결과를 생성한다."""

    DEFAULT_LIMIT = 120
    MAX_LIMIT = 150

    @classmethod
    def search(cls, tag_values: List[str], limit: int | None = None) -> Dict[str, Any]:
        clean_tags = cls._normalize_tags(tag_values)
        safe_limit = cls._normalize_limit(limit)

        readiness = cls._check_graph_readiness()
        if readiness is not None:
            return cls._empty_response(clean_tags, status="empty_data", data_state=readiness)

        if not clean_tags:
            return {
                "status": "no_query_match",
                "query": {
                    "tags": [],
                    "resolved_tags": [],
                    "unresolved_tags": [],
                },
                "items": [],
                "meta": {
                    "returned": 0,
                    "data_state": "missing_query",
                    "message": "검색 태그가 필요합니다.",
                },
            }

        resolved_tags = list(Tags.objects.filter(tag_key__in=clean_tags, is_deleted=False))
        resolved_keys = {tag.tag_key for tag in resolved_tags}
        unresolved_tags = [tag for tag in clean_tags if tag not in resolved_keys]

        if not resolved_tags:
            return {
                "status": "no_query_match",
                "query": {
                    "tags": clean_tags,
                    "resolved_tags": [],
                    "unresolved_tags": unresolved_tags,
                },
                "items": [],
                "meta": {
                    "returned": 0,
                    "data_state": "query_tags_not_found",
                    "message": "검색한 태그가 아직 등록되지 않았습니다.",
                },
            }

        edges = (
            MusicTags.objects.filter(
                tag__in=resolved_tags,
                is_deleted=False,
                music__is_deleted=False,
                tag__is_deleted=False,
            )
            .select_related("music", "music__artist", "music__album", "tag")
            .order_by("-score")
        )

        candidates = cls._build_direct_candidates(edges)
        if not candidates:
            return {
                "status": "no_results",
                "query": cls._query_payload(clean_tags, resolved_tags, unresolved_tags),
                "items": [],
                "meta": {
                    "returned": 0,
                    "data_state": "no_connected_tracks",
                    "message": "태그는 있지만 연결된 곡이 없습니다.",
                },
            }

        items = cls._rank_and_serialize(candidates, safe_limit)

        return {
            "status": "ok",
            "query": cls._query_payload(clean_tags, resolved_tags, unresolved_tags),
            "items": items,
            "meta": {
                "returned": len(items),
                "total_candidates": len(candidates),
                "data_state": "ready",
                "graph_version": "direct-tag-v1",
            },
        }

    @classmethod
    def _normalize_tags(cls, tag_values: List[str]) -> List[str]:
        seen = set()
        normalized = []
        for raw_tag in tag_values:
            for part in str(raw_tag).split(","):
                tag = part.strip().lstrip("#").strip()
                if tag and tag not in seen:
                    normalized.append(tag)
                    seen.add(tag)
        return normalized[:3]

    @classmethod
    def _normalize_limit(cls, limit: int | None) -> int:
        if limit is None:
            return cls.DEFAULT_LIMIT
        try:
            parsed = int(limit)
        except (TypeError, ValueError):
            return cls.DEFAULT_LIMIT
        return max(1, min(parsed, cls.MAX_LIMIT))

    @classmethod
    def _check_graph_readiness(cls) -> str | None:
        if not Music.objects.exists():
            return "missing_music"
        if not Tags.objects.exists():
            return "missing_tags"
        if not MusicTags.objects.exists():
            return "missing_music_tags"
        return None

    @classmethod
    def _empty_response(cls, tags: List[str], status: str, data_state: str) -> Dict[str, Any]:
        messages = {
            "missing_music": "GraphRAG를 위한 음악 데이터가 아직 없습니다.",
            "missing_tags": "GraphRAG를 위한 태그 데이터가 아직 없습니다.",
            "missing_music_tags": "GraphRAG를 위한 곡-태그 연결 데이터가 아직 없습니다.",
        }
        return {
            "status": status,
            "query": {
                "tags": tags,
                "resolved_tags": [],
                "unresolved_tags": tags,
            },
            "items": [],
            "meta": {
                "returned": 0,
                "data_state": data_state,
                "message": messages.get(data_state, "GraphRAG 데이터가 아직 준비되지 않았습니다."),
            },
        }

    @classmethod
    def _query_payload(cls, tags: List[str], resolved_tags: List[Tags], unresolved_tags: List[str]) -> Dict[str, Any]:
        return {
            "tags": tags,
            "resolved_tags": [
                {
                    "tag_id": tag.tag_id,
                    "tag_key": tag.tag_key,
                    "tag_name": tag.tag_key,
                }
                for tag in resolved_tags
            ],
            "unresolved_tags": unresolved_tags,
        }

    @classmethod
    def _build_direct_candidates(cls, edges) -> Dict[int, Dict[str, Any]]:
        candidates: Dict[int, Dict[str, Any]] = {}
        matched_tags_by_music: Dict[int, Dict[str, float]] = defaultdict(dict)

        for edge in edges:
            if not edge.music:
                continue

            music_id = edge.music.music_id
            score = float(edge.score or 0.0)
            matched_tags_by_music[music_id][edge.tag.tag_key] = max(
                matched_tags_by_music[music_id].get(edge.tag.tag_key, 0.0),
                score,
            )

            if music_id not in candidates:
                candidates[music_id] = {
                    "music": edge.music,
                    "direct_tag_score": score,
                }
            else:
                candidates[music_id]["direct_tag_score"] = max(
                    candidates[music_id]["direct_tag_score"],
                    score,
                )

        for music_id, candidate in candidates.items():
            candidate["matched_tags"] = [
                {"tag_key": tag_key, "tag_name": tag_key, "score": score}
                for tag_key, score in sorted(
                    matched_tags_by_music[music_id].items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ]

        return candidates

    @classmethod
    def _rank_and_serialize(cls, candidates: Dict[int, Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        raw_scores = [candidate["direct_tag_score"] for candidate in candidates.values()]
        min_score = min(raw_scores)
        max_score = max(raw_scores)

        rows = []
        for candidate in candidates.values():
            music = candidate["music"]
            relevance_score = cls._normalize_score(candidate["direct_tag_score"], min_score, max_score)
            visual_weight = math.sqrt(relevance_score)
            album = music.album
            artist = music.artist

            rows.append(
                {
                    "music_id": music.music_id,
                    "music_name": music.music_name,
                    "artist_name": artist.artist_name if artist else None,
                    "album_name": album.album_name if album else None,
                    "audio_url": music.audio_url,
                    "image_large_square": album.image_large_square if album else None,
                    "image_square": album.image_square if album else None,
                    "album_image": album.album_image if album else None,
                    "relevance_score": round(relevance_score, 4),
                    "visual_weight": round(visual_weight, 4),
                    "cluster": candidate["matched_tags"][0]["tag_key"] if candidate["matched_tags"] else None,
                    "matched_tags": candidate["matched_tags"],
                    "explanations": [
                        {
                            "type": "direct_tag",
                            "path": [
                                f"tag:{matched_tag['tag_key']}",
                                f"music:{music.music_id}",
                            ],
                            "weight": round(matched_tag["score"], 4),
                            "reason": "검색 태그와 직접 연결된 곡입니다.",
                        }
                        for matched_tag in candidate["matched_tags"][:3]
                    ],
                }
            )

        rows.sort(key=lambda row: (row["relevance_score"], row["music_id"]), reverse=True)
        return rows[:limit]

    @classmethod
    def _normalize_score(cls, score: float, min_score: float, max_score: float) -> float:
        if max_score == min_score:
            return 0.5
        return max(0.0, min((score - min_score) / (max_score - min_score), 1.0))
