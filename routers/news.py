from datetime import datetime
from typing import List
import uuid

from fastapi import (
    APIRouter, Depends, HTTPException, Query,
    UploadFile, File, status
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from config import settings
from database import get_db
from models import News, User
from schemas import NewsCreate, NewsUpdate, NewsResponse, NewsListResponse
from auth import get_current_user, get_current_subscribed_user  # Updated import
from utils import upload_news_image

router = APIRouter(prefix="/news", tags=["news"])

# ─────────────────────────────
# Utility
# ─────────────────────────────
async def get_news_by_id(news_id: uuid.UUID, db: AsyncSession) -> News:
    result = await db.execute(select(News).where(News.id == news_id))
    news = result.scalars().first()
    if not news:
        raise HTTPException(status_code=404, detail="News item not found")
    return news


# ─────────────────────────────
# Create News - No subscription required (authors/admins only)
# ─────────────────────────────
@router.post("/", response_model=NewsResponse)
async def create_news(
    news_data: NewsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # Regular auth check
):
    """Create a new news article"""
    db_news = News(
        title=news_data.title,
        content=news_data.content,
        image_url=news_data.image_url,
        is_published=news_data.is_published,
        author_id=current_user.id,
        created_at=datetime.utcnow()
    )
    db.add(db_news)
    await db.commit()
    await db.refresh(db_news)
    return db_news


# ─────────────────────────────
# Get Paginated News List - Requires subscription
# ─────────────────────────────
@router.get("/", response_model=NewsListResponse)
async def get_news_list(
    page: int = Query(1, gt=0),
    size: int = Query(10, gt=0, le=100),
    published_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_subscribed_user),  # Subscription check
):
    """Get paginated list of news items (subscribers only)"""
    query = select(News)
    if published_only:
        query = query.where(News.is_published == True)

    total_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_query)).scalar_one()

    items_query = query.order_by(News.created_at.desc()).offset((page - 1) * size).limit(size)
    items = (await db.execute(items_query)).scalars().all()

    return NewsListResponse(items=items, total=total, page=page, size=size)


# ─────────────────────────────
# Get Single News by ID - Requires subscription
# ─────────────────────────────
@router.get("/{news_id}", response_model=NewsResponse)
async def get_news(
    news_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_subscribed_user),  # Subscription check
):
    """Get a single news item by ID (subscribers only)"""
    return await get_news_by_id(news_id, db)


# ─────────────────────────────
# Update News - No subscription required (authors/admins only)
# ─────────────────────────────
@router.put("/{news_id}", response_model=NewsResponse)
async def update_news(
    news_id: uuid.UUID,
    news_data: NewsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # Regular auth check
):
    """Update a news item"""
    news = await get_news_by_id(news_id, db)

    if news.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to update this news item")

    for field, value in news_data.dict(exclude_unset=True).items():
        setattr(news, field, value)

    news.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(news)
    return news


# ─────────────────────────────
# Delete News - No subscription required (authors/admins only)
# ─────────────────────────────
@router.delete("/{news_id}", status_code=204)
async def delete_news(
    news_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # Regular auth check
):
    """Delete a news item"""
    news = await get_news_by_id(news_id, db)

    if news.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this news item")

    await db.delete(news)
    await db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)


# ─────────────────────────────
# Get Latest News - Requires subscription
# ─────────────────────────────
@router.get("/latest/", response_model=List[NewsResponse])
async def get_latest_news(
    limit: int = Query(5, gt=0, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_subscribed_user),  # Subscription check
):
    """Get latest news articles (subscribers only)"""
    result = await db.execute(
        select(News)
        .where(News.is_published == True)
        .order_by(News.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


# ─────────────────────────────
# Upload News Image - No subscription required (authors/admins only)
# ─────────────────────────────
@router.post("/upload-image/")
async def upload_news_image_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),  # Regular auth check
):
    """Upload an image for a news article"""
    image_url = await upload_news_image(file)
    return {"url": image_url}


# ─────────────────────────────
# Search News - Requires subscription
# ─────────────────────────────
@router.get("/search/", response_model=NewsListResponse)
async def search_news(
    query: str = Query(..., min_length=1),
    page: int = Query(1, gt=0),
    size: int = Query(10, gt=0, le=100),
    published_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_subscribed_user),  # Subscription check
):
    """Search news articles by title or content (subscribers only)"""
    q = select(News)
    if published_only:
        q = q.where(News.is_published == True)

    q = q.where(
        or_(
            News.title.ilike(f"%{query}%"),
            News.content.ilike(f"%{query}%")
        )
    )

    total_query = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_query)).scalar_one()

    items_query = q.order_by(News.created_at.desc()).offset((page - 1) * size).limit(size)
    items = (await db.execute(items_query)).scalars().all()

    return NewsListResponse(items=items, total=total, page=page, size=size)