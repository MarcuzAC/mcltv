from datetime import datetime, timedelta
from typing import List, Dict
from uuid import UUID
from fastapi import (
    APIRouter, Depends, HTTPException, Query,
    UploadFile, File, status, Form
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, extract
from config import settings
from database import get_db
from models import News, User
from schemas import NewsCreate, NewsUpdate, NewsResponse, NewsListResponse
from auth import get_current_user
from utils import upload_news_image

router = APIRouter(prefix="/news", tags=["news"])

# ─────────────────────────────
# Utility
# ─────────────────────────────
async def get_news_by_id(news_id: UUID, db: AsyncSession) -> News:
    result = await db.execute(select(News).where(News.id == news_id))
    news = result.scalars().first()
    if not news:
        raise HTTPException(status_code=404, detail="News item not found")
    return news

# ─────────────────────────────
# Create News
# ─────────────────────────────
@router.post("/", response_model=NewsResponse)
async def create_news(
    title: str = Form(..., min_length=1, max_length=255),
    content: str = Form(..., min_length=1),
    is_published: bool = Form(False),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new news article with a required title, content, and image."""
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_url = await upload_news_image(image)

    db_news = News(
        title=title,
        content=content,
        image_url=image_url,
        is_published=is_published,
        author_id=current_user.id,
        created_at=datetime.utcnow(),
        published_at=datetime.utcnow() if is_published else None
    )
    db.add(db_news)
    await db.commit()
    await db.refresh(db_news)
    return db_news

# ─────────────────────────────
# Get Paginated News List
# ─────────────────────────────
@router.get("/", response_model=NewsListResponse)
async def get_news_list(
    page: int = Query(1, gt=0),
    size: int = Query(10, gt=0, le=100),
    published_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of news items."""
    query = select(News)
    if published_only:
        query = query.where(News.is_published == True)

    total_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_query)).scalar_one()

    items_query = query.order_by(
        News.published_at.desc() if published_only else News.created_at.desc()
    ).offset((page - 1) * size).limit(size)
    
    items = (await db.execute(items_query)).scalars().all()
    return NewsListResponse(items=items, total=total, page=page, size=size)

# ─────────────────────────────
# Get Single News by ID
# ─────────────────────────────
@router.get("/{news_id}", response_model=NewsResponse)
async def get_news(
    news_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single news item by ID."""
    return await get_news_by_id(news_id, db)

# ─────────────────────────────
# Update News
# ─────────────────────────────
@router.put("/{news_id}", response_model=NewsResponse)
async def update_news(
    news_id: UUID,
    title: str | None = Form(None, min_length=1, max_length=255),
    content: str | None = Form(None, min_length=1),
    is_published: bool | None = Form(None),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a news item with optional image upload (authors/admins only)."""
    news = await get_news_by_id(news_id, db)

    if news.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to update this news item")

    if title is not None:
        news.title = title
    if content is not None:
        news.content = content
    if is_published is not None:
        news.is_published = is_published
        # Update published_at when publication status changes
        if is_published and not news.published_at:
            news.published_at = datetime.utcnow()
        elif not is_published:
            news.published_at = None
    if image is not None:
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        news.image_url = await upload_news_image(image)

    news.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(news)
    return news

# ─────────────────────────────
# Delete News
# ─────────────────────────────
@router.delete("/{news_id}", status_code=204)
async def delete_news(
    news_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a news item (authors/admins only)."""
    news = await get_news_by_id(news_id, db)

    if news.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this news item")

    await db.delete(news)
    await db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)

# ─────────────────────────────
# Get Latest News
# ─────────────────────────────
@router.get("/latest/", response_model=List[NewsResponse])
async def get_latest_news(
    limit: int = Query(5, gt=0, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Get latest published news articles."""
    result = await db.execute(
        select(News)
        .where(News.is_published == True)
        .order_by(News.published_at.desc())
        .limit(limit)
    )
    return result.scalars().all()

# ─────────────────────────────
# Upload News Image
# ─────────────────────────────
@router.post("/upload-image/")
async def upload_news_image_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload an image for a news article (authors/admins only)."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    image_url = await upload_news_image(file)
    return {"url": image_url}

# ─────────────────────────────
# News Statistics
# ─────────────────────────────
@router.get("/stats/count")
async def get_news_count(
    db: AsyncSession = Depends(get_db),
    published_only: bool = Query(True)
):
    """Get total count of news articles (optionally filtered by published status)."""
    query = select(func.count(News.id))
    if published_only:
        query = query.where(News.is_published == True)
    
    total_news = (await db.execute(query)).scalar_one()
    return {"total_news": total_news}

@router.get("/stats/growth", response_model=List[Dict[str, int]])
async def get_news_growth(
    months: int = Query(12, gt=0, le=36, description="Number of months to include"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get news publication growth statistics.
    Returns monthly counts of published news articles.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30*months)  # Approximate months
    
    result = await db.execute(
        select([
            extract('year', News.published_at).label('year'),
            extract('month', News.published_at).label('month'),
            func.count(News.id).label('count')
        ])
        .where(News.is_published == True)
        .where(News.published_at != None)
        .where(News.published_at.between(start_date, end_date))
        .group_by('year', 'month')
        .order_by('year', 'month')
    )
    
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    formatted_data = []
    for year, month, count in result:
        formatted_data.append({
            "month": f"{month_names[int(month)-1]} {int(year)}",
            "count": count
        })
    
    return formatted_data

@router.get("/stats/publication")
async def get_publication_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get news publication statistics."""
    result = await db.execute(
        select([
            func.count().filter(News.is_published == True).label("published_count"),
            func.count().filter(News.is_published == False).label("draft_count"),
            func.count().label("total_count")
        ])
    )
    stats = result.first()
    return {
        "published": stats.published_count,
        "drafts": stats.draft_count,
        "total": stats.total_count
    }

# ─────────────────────────────
# Search News
# ─────────────────────────────
@router.get("/search/", response_model=NewsListResponse)
async def search_news(
    query: str = Query(..., min_length=1),
    page: int = Query(1, gt=0),
    size: int = Query(10, gt=0, le=100),
    published_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """Search news articles by title or content."""
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