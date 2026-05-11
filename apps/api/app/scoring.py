from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import log10
from typing import Optional


@dataclass
class MetricSnapshotInput:
    like_count: int = 0
    comment_count: int = 0
    view_count: int = 0
    rank_position: Optional[int] = None
    collected_at: Optional[datetime] = None


@dataclass
class ScoreOutput:
    viral_score: float
    velocity_score: float
    debate_score: float
    risk_score: float = 20.0


def _clamp(value: float, min_value: float = 0, max_value: float = 100) -> float:
    return max(min_value, min(max_value, value))


def _log_score(value: int, scale: float) -> float:
    if value <= 0:
        return 0
    return _clamp(log10(value + 1) * scale)


def _per_hour_delta(current: int, previous: int, hours_elapsed: float) -> float:
    if hours_elapsed <= 0:
        return 0
    return max(0, current - previous) / hours_elapsed


def calculate_scores(current: MetricSnapshotInput, previous: Optional[MetricSnapshotInput] = None) -> ScoreOutput:
    like_score = _log_score(current.like_count, 18)
    comment_score = _log_score(current.comment_count, 22)
    view_score = _log_score(current.view_count, 12)

    current_reaction_volume = _clamp((like_score * 0.35) + (comment_score * 0.45) + (view_score * 0.2))

    rank_score = 50.0
    if current.rank_position:
        rank_score = _clamp(100 - (current.rank_position - 1) * 3)

    velocity_score = 0.0
    if previous and current.collected_at and previous.collected_at:
        hours = (current.collected_at - previous.collected_at).total_seconds() / 3600
        likes_per_hour = _per_hour_delta(current.like_count, previous.like_count, hours)
        comments_per_hour = _per_hour_delta(current.comment_count, previous.comment_count, hours)
        views_per_hour = _per_hour_delta(current.view_count, previous.view_count, hours)
        velocity_score = _clamp(
            _log_score(int(likes_per_hour), 18) * 0.35
            + _log_score(int(comments_per_hour), 28) * 0.5
            + _log_score(int(views_per_hour), 10) * 0.15
        )

    debate_by_views = (current.comment_count / current.view_count) if current.view_count else 0
    debate_by_likes = (current.comment_count / current.like_count) if current.like_count else 0
    debate_score = _clamp((debate_by_views * 2500) + (debate_by_likes * 80) + (comment_score * 0.25))

    viral_score = _clamp(
        current_reaction_volume * 0.30
        + velocity_score * 0.35
        + debate_score * 0.20
        + rank_score * 0.15
    )

    return ScoreOutput(
        viral_score=round(viral_score, 2),
        velocity_score=round(velocity_score, 2),
        debate_score=round(debate_score, 2),
    )
