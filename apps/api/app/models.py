from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SourceType(str, Enum):
    reddit = "reddit"
    rss = "rss"
    web = "web"


class SourceRiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    blocked = "blocked"


class StoryStatus(str, Enum):
    collected = "collected"
    analyzed = "analyzed"
    approved = "approved"
    scripted = "scripted"
    rejected = "rejected"
    archived = "archived"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    platform: Mapped[str] = mapped_column(String(50), index=True)
    source_name: Mapped[str] = mapped_column(String(200), index=True)
    source_url: Mapped[str] = mapped_column(String(1000), unique=True)
    source_type: Mapped[SourceType] = mapped_column(SqlEnum(SourceType), default=SourceType.rss)
    collection_method: Mapped[str] = mapped_column(String(100), default="metadata")
    risk_level: Mapped[SourceRiskLevel] = mapped_column(SqlEnum(SourceRiskLevel), default=SourceRiskLevel.low)
    crawl_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    posts: Mapped[list["CollectedPost"]] = relationship(back_populates="source")


class CollectedPost(Base):
    __tablename__ = "collected_posts"
    __table_args__ = (UniqueConstraint("platform", "post_external_id", name="uq_platform_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    platform: Mapped[str] = mapped_column(String(50), index=True)
    post_external_id: Mapped[str] = mapped_column(String(500), index=True)
    post_url: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(500), index=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status: Mapped[StoryStatus] = mapped_column(SqlEnum(StoryStatus), default=StoryStatus.collected)

    source: Mapped[Source] = relationship(back_populates="posts")
    snapshots: Mapped[list["PostMetricSnapshot"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    score: Mapped[Optional["StoryScore"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    analysis: Mapped[Optional["StoryAnalysis"]] = relationship(back_populates="post", cascade="all, delete-orphan")


class PostMetricSnapshot(Base):
    __tablename__ = "post_metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("collected_posts.id"), index=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    rank_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    post: Mapped[CollectedPost] = relationship(back_populates="snapshots")


class StoryScore(Base):
    __tablename__ = "story_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("collected_posts.id"), unique=True, index=True)
    viral_score: Mapped[float] = mapped_column(Float, default=0)
    velocity_score: Mapped[float] = mapped_column(Float, default=0)
    debate_score: Mapped[float] = mapped_column(Float, default=0)
    conflict_score: Mapped[float] = mapped_column(Float, default=0)
    shorts_score: Mapped[float] = mapped_column(Float, default=0)
    longform_score: Mapped[float] = mapped_column(Float, default=0)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped[CollectedPost] = relationship(back_populates="score")


class StoryAnalysis(Base):
    __tablename__ = "story_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("collected_posts.id"), unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    core_conflict: Mapped[str] = mapped_column(Text, default="")
    red_flags: Mapped[str] = mapped_column(Text, default="")
    debate_point: Mapped[str] = mapped_column(Text, default="")
    audience_emotion: Mapped[str] = mapped_column(Text, default="")
    hidden_pattern: Mapped[str] = mapped_column(Text, default="")
    youtube_angle: Mapped[str] = mapped_column(Text, default="")
    risk_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped[CollectedPost] = relationship(back_populates="analysis")


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("collected_posts.id"), index=True)
    language: Mapped[str] = mapped_column(String(20), default="en")
    format: Mapped[str] = mapped_column(String(50), default="shorts")
    tone: Mapped[str] = mapped_column(String(100), default="storytime")
    title_options: Mapped[str] = mapped_column(Text, default="")
    thumbnail_options: Mapped[str] = mapped_column(Text, default="")
    hook_options: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    comment_question: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
