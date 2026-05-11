from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Iterable, Optional

import feedparser
from dateutil import parser as date_parser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CollectedPost, PostMetricSnapshot, Source, StoryScore
from app.scoring import MetricSnapshotInput, calculate_scores


@dataclass
class CollectedItem:
    external_id: str
    title: str
    url: str
    posted_at: Optional[datetime]
    like_count: int = 0
    comment_count: int = 0
    view_count: int = 0
    rank_position: Optional[int] = None


@dataclass
class CollectionResult:
    source_id: int
    source_name: str
    created_posts: int = 0
    updated_posts: int = 0
    snapshots: int = 0


def _stable_external_id(url: str, title: str) -> str:
    return sha256(f"{url}|{title}".encode("utf-8")).hexdigest()


def _parse_datetime(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = date_parser.parse(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def collect_rss_items(source: Source) -> list[CollectedItem]:
    feed = feedparser.parse(source.source_url)
    items: list[CollectedItem] = []

    for index, entry in enumerate(feed.entries, start=1):
        title = getattr(entry, "title", "").strip()
        url = getattr(entry, "link", "").strip()
        if not title or not url:
            continue

        published = getattr(entry, "published", None) or getattr(entry, "updated", None)
        posted_at = _parse_datetime(published)
        external_id = getattr(entry, "id", None) or _stable_external_id(url, title)

        items.append(
            CollectedItem(
                external_id=external_id,
                title=title[:500],
                url=url,
                posted_at=posted_at,
                rank_position=index,
            )
        )

    return items


def collect_source(db: Session, source: Source) -> CollectionResult:
    if source.source_type.value == "rss":
        items = collect_rss_items(source)
    else:
        items = []

    result = CollectionResult(source_id=source.id, source_name=source.source_name)

    for item in items:
        existing = db.execute(
            select(CollectedPost).where(
                CollectedPost.platform == source.platform,
                CollectedPost.post_external_id == item.external_id,
            )
        ).scalar_one_or_none()

        if existing is None:
            post = CollectedPost(
                source_id=source.id,
                platform=source.platform,
                post_external_id=item.external_id,
                post_url=item.url,
                title=item.title,
                posted_at=item.posted_at,
            )
            db.add(post)
            db.flush()
            result.created_posts += 1
        else:
            post = existing
            post.title = item.title
            post.post_url = item.url
            result.updated_posts += 1

        snapshot = PostMetricSnapshot(
            post_id=post.id,
            like_count=item.like_count,
            comment_count=item.comment_count,
            view_count=item.view_count,
            rank_position=item.rank_position,
        )
        db.add(snapshot)
        db.flush()
        result.snapshots += 1

        previous_snapshot = (
            db.execute(
                select(PostMetricSnapshot)
                .where(PostMetricSnapshot.post_id == post.id, PostMetricSnapshot.id != snapshot.id)
                .order_by(PostMetricSnapshot.collected_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

        current_input = MetricSnapshotInput(
            like_count=snapshot.like_count,
            comment_count=snapshot.comment_count,
            view_count=snapshot.view_count,
            rank_position=snapshot.rank_position,
            collected_at=snapshot.collected_at,
        )
        previous_input = None
        if previous_snapshot:
            previous_input = MetricSnapshotInput(
                like_count=previous_snapshot.like_count,
                comment_count=previous_snapshot.comment_count,
                view_count=previous_snapshot.view_count,
                rank_position=previous_snapshot.rank_position,
                collected_at=previous_snapshot.collected_at,
            )

        score_output = calculate_scores(current_input, previous_input)
        score = db.execute(select(StoryScore).where(StoryScore.post_id == post.id)).scalar_one_or_none()
        if score is None:
            score = StoryScore(post_id=post.id)
            db.add(score)

        score.viral_score = score_output.viral_score
        score.velocity_score = score_output.velocity_score
        score.debate_score = score_output.debate_score
        score.risk_score = score_output.risk_score

    db.commit()
    return result
