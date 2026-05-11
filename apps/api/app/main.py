from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.analysis import build_stub_analysis, build_stub_shorts_script
from app.collector import collect_source
from app.config import settings
from app.db import Base, engine, get_db
from app.models import CollectedPost, PostMetricSnapshot, Script, Source, StoryAnalysis, StoryScore, StoryStatus
from app.schemas import CollectSourceResult, SourceCreate, SourceRead, StoryCardRead

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.post("/sources", response_model=SourceRead)
def create_source(payload: SourceCreate, db: Annotated[Session, Depends(get_db)]):
    source = Source(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@app.get("/sources", response_model=list[SourceRead])
def list_sources(db: Annotated[Session, Depends(get_db)]):
    return db.execute(select(Source).order_by(Source.created_at.desc())).scalars().all()


@app.post("/sources/{source_id}/collect", response_model=CollectSourceResult)
def collect_single_source(source_id: int, db: Annotated[Session, Depends(get_db)]):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    result = collect_source(db, source)
    return CollectSourceResult(**result.__dict__)


@app.post("/collect/run", response_model=list[CollectSourceResult])
def collect_all_active_sources(db: Annotated[Session, Depends(get_db)]):
    sources = db.execute(select(Source).where(Source.is_active.is_(True))).scalars().all()
    results = []
    for source in sources:
        result = collect_source(db, source)
        results.append(CollectSourceResult(**result.__dict__))
    return results


def _story_card(post: CollectedPost) -> StoryCardRead:
    latest_snapshot = None
    if post.snapshots:
        latest_snapshot = sorted(post.snapshots, key=lambda snapshot: snapshot.collected_at, reverse=True)[0]
    return StoryCardRead(
        id=post.id,
        platform=post.platform,
        post_external_id=post.post_external_id,
        post_url=post.post_url,
        title=post.title,
        posted_at=post.posted_at,
        status=post.status,
        latest_snapshot=latest_snapshot,
        score=post.score,
    )


@app.get("/stories", response_model=list[StoryCardRead])
def list_stories(db: Annotated[Session, Depends(get_db)], limit: int = 50):
    posts = (
        db.execute(
            select(CollectedPost)
            .options(
                selectinload(CollectedPost.snapshots),
                selectinload(CollectedPost.score),
            )
            .join(StoryScore, StoryScore.post_id == CollectedPost.id, isouter=True)
            .order_by(StoryScore.viral_score.desc().nullslast(), CollectedPost.first_collected_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [_story_card(post) for post in posts]


@app.get("/dashboard/summary")
def dashboard_summary(db: Annotated[Session, Depends(get_db)]):
    total_sources = db.scalar(select(func.count(Source.id))) or 0
    active_sources = db.scalar(select(func.count(Source.id)).where(Source.is_active.is_(True))) or 0
    total_stories = db.scalar(select(func.count(CollectedPost.id))) or 0
    total_snapshots = db.scalar(select(func.count(PostMetricSnapshot.id))) or 0
    scripted_stories = db.scalar(select(func.count(CollectedPost.id)).where(CollectedPost.status == StoryStatus.scripted)) or 0
    analyzed_stories = db.scalar(select(func.count(CollectedPost.id)).where(CollectedPost.status == StoryStatus.analyzed)) or 0
    avg_viral_score = db.scalar(select(func.avg(StoryScore.viral_score))) or 0

    return {
        "total_sources": total_sources,
        "active_sources": active_sources,
        "total_stories": total_stories,
        "total_snapshots": total_snapshots,
        "analyzed_stories": analyzed_stories,
        "scripted_stories": scripted_stories,
        "avg_viral_score": round(float(avg_viral_score), 2),
    }


@app.post("/stories/{post_id}/analyze")
def analyze_story(post_id: int, db: Annotated[Session, Depends(get_db)]):
    post = db.get(CollectedPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Story not found")

    payload = build_stub_analysis(post)
    analysis = db.execute(select(StoryAnalysis).where(StoryAnalysis.post_id == post.id)).scalar_one_or_none()
    if analysis is None:
        analysis = StoryAnalysis(post_id=post.id)
        db.add(analysis)

    for key, value in payload.items():
        setattr(analysis, key, value)

    post.status = StoryStatus.analyzed
    db.commit()
    db.refresh(analysis)
    return payload


@app.post("/stories/{post_id}/scripts/shorts")
def generate_shorts_script(post_id: int, db: Annotated[Session, Depends(get_db)]):
    post = db.get(CollectedPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Story not found")

    payload = build_stub_shorts_script(post.title)
    script = Script(post_id=post.id, language="en", format="shorts", tone="storytime", **payload)
    db.add(script)
    post.status = StoryStatus.scripted
    db.commit()
    db.refresh(script)
    return {
        "script_id": script.id,
        **payload,
    }
