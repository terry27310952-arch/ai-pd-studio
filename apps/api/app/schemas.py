from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import SourceRiskLevel, SourceType, StoryStatus


class SourceCreate(BaseModel):
    platform: str = Field(..., examples=["reddit"])
    source_name: str = Field(..., examples=["r/relationship_advice"])
    source_url: str
    source_type: SourceType = SourceType.rss
    collection_method: str = "metadata"
    risk_level: SourceRiskLevel = SourceRiskLevel.low
    crawl_interval_minutes: int = 60
    is_active: bool = True


class SourceRead(SourceCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SnapshotRead(BaseModel):
    id: int
    like_count: int
    comment_count: int
    view_count: int
    rank_position: Optional[int] = None
    collected_at: datetime

    class Config:
        from_attributes = True


class ScoreRead(BaseModel):
    viral_score: float
    velocity_score: float
    debate_score: float
    conflict_score: float
    shorts_score: float
    longform_score: float
    risk_score: float
    calculated_at: datetime

    class Config:
        from_attributes = True


class StoryCardRead(BaseModel):
    id: int
    platform: str
    post_external_id: str
    post_url: str
    title: str
    posted_at: Optional[datetime] = None
    status: StoryStatus
    latest_snapshot: Optional[SnapshotRead] = None
    score: Optional[ScoreRead] = None

    class Config:
        from_attributes = True


class CollectSourceResult(BaseModel):
    source_id: int
    source_name: str
    created_posts: int
    updated_posts: int
    snapshots: int
