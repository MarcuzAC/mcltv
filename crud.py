from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, func, update
import models
import schemas
import uuid
from security import get_password_hash
from sqlalchemy.orm import joinedload, selectinload
from fastapi import HTTPException

# User Operations
async def get_all_users_except_me(db: AsyncSession, my_user_id: uuid.UUID, limit: int) -> List[models.User]:
    result = await db.execute(select(models.User).filter(models.User.id != my_user_id).limit(limit))
    return result.scalars().all()

async def get_user(db: AsyncSession, user_id: uuid.UUID) -> Optional[models.User]:
    result = await db.execute(select(models.User).filter(models.User.id == user_id))
    return result.scalars().first()

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).filter(models.User.username == username))
    return result.scalars().first()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).filter(models.User.email == email))
    return result.scalars().first()

async def update_user(db: AsyncSession, user: models.User, user_update: schemas.UserUpdate) -> models.User:
    for key, value in user_update.dict(exclude_unset=True).items():
        setattr(user, key, value)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def delete_user(db: AsyncSession, user: models.User) -> None:
    await db.delete(user)
    await db.commit()

# Enhanced Category Operations
async def get_all_categories_with_video_counts(db: AsyncSession) -> List[Dict[str, Any]]:
    """Get all categories with their video counts"""
    result = await db.execute(
        select(
            models.Category,
            func.count(models.Video.id).label("video_count")
        )
        .join(models.Video, models.Video.category_id == models.Category.id, isouter=True)
        .group_by(models.Category.id)
        .order_by(models.Category.name)
    )
    return [{"category": category, "video_count": count} for category, count in result.all()]

async def get_category_with_video_count(db: AsyncSession, category_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Get a single category with its video count"""
    result = await db.execute(
        select(
            models.Category,
            func.count(models.Video.id).label("video_count")
        )
        .join(models.Video, models.Video.category_id == models.Category.id, isouter=True)
        .where(models.Category.id == category_id)
        .group_by(models.Category.id)
    )
    row = result.first()
    return {"category": row[0], "video_count": row[1]} if row else None

async def get_all_categories(db: AsyncSession) -> List[models.Category]:
    result = await db.execute(select(models.Category))
    return result.scalars().all()

async def get_category(db: AsyncSession, category_id: uuid.UUID) -> Optional[models.Category]:
    result = await db.execute(select(models.Category).filter(models.Category.id == category_id))
    return result.scalars().first()

async def get_category_by_name(db: AsyncSession, name: str) -> Optional[models.Category]:
    result = await db.execute(
        select(models.Category)
        .where(func.lower(models.Category.name) == func.lower(name))
    )
    return result.scalars().first()

async def create_category(db: AsyncSession, category: schemas.CategoryCreate) -> models.Category:
    db_category = models.Category(**category.dict())
    db.add(db_category)
    await db.commit()
    await db.refresh(db_category)
    return db_category

async def update_category(
    db: AsyncSession, 
    db_category: models.Category, 
    category_update: schemas.CategoryCreate
) -> models.Category:
    db_category.name = category_update.name
    await db.commit()
    await db.refresh(db_category)
    return db_category

async def delete_category(db: AsyncSession, category: models.Category) -> None:
    await db.delete(category)
    await db.commit()

# Video Operations
async def get_all_videos(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100, 
    category_id: Optional[uuid.UUID] = None
) -> List[Dict[str, Any]]:
    query = (
        select(
            models.Video.id, 
            models.Video.title, 
            models.Video.created_date,
            models.Video.vimeo_url, 
            models.Video.vimeo_id, 
            models.Video.thumbnail_url,
            models.Category.name.label("category")
        )
        .join(models.Category, models.Video.category_id == models.Category.id, isouter=True)
        .offset(skip)
        .limit(limit)
    )
    
    if category_id:
        if not await get_category(db, category_id):
            raise HTTPException(status_code=404, detail="Category not found")
        query = query.where(models.Video.category_id == category_id)
    
    result = await db.execute(query)
    videos = result.all()
    
    return [
        {
            "id": v.id,
            "title": v.title,
            "created_date": v.created_date,
            "vimeo_url": v.vimeo_url,
            "vimeo_id": v.vimeo_id,
            "thumbnail_url": v.thumbnail_url,
            "category": v.category,
            "like_count": await get_like_count(db, v.id),
            "comment_count": await get_comment_count(db, v.id),
        }
        for v in videos
    ]

async def get_video(db: AsyncSession, video_id: uuid.UUID) -> Optional[models.Video]:
    result = await db.execute(
        select(models.Video)
        .options(
            joinedload(models.Video.category),
            joinedload(models.Video.likes),
            joinedload(models.Video.comments).joinedload(models.Comment.user)
        )
        .filter(models.Video.id == video_id)
    )
    return result.scalars().first()

async def create_video(
    db: AsyncSession, 
    video: schemas.VideoCreate, 
    vimeo_url: str, 
    vimeo_id: str, 
    thumbnail_url: Optional[str] = None
) -> models.Video:
    db_video = models.Video(
        **video.dict(),
        vimeo_url=vimeo_url,
        vimeo_id=vimeo_id,
        thumbnail_url=thumbnail_url
    )
    db.add(db_video)
    await db.commit()
    await db.refresh(db_video)
    return db_video

async def update_video(
    db: AsyncSession, 
    db_video: models.Video, 
    video_update: schemas.VideoUpdate
) -> models.Video:
    update_data = video_update.model_dump(exclude_unset=True)
    allowed_fields = {"title", "category_id", "thumbnail_url"}
    update_data = {k: v for k, v in update_data.items() if k in allowed_fields}

    for key, value in update_data.items():
        setattr(db_video, key, value)

    db.add(db_video)
    await db.commit()
    await db.refresh(db_video)
    return db_video

async def delete_video(db: AsyncSession, video: models.Video) -> Dict[str, str]:
    await db.delete(video)
    await db.commit()
    return {"detail": "Video deleted successfully"}

async def get_recent_videos(db: AsyncSession, limit: int = 5) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(models.Video)
        .options(joinedload(models.Video.category))
        .order_by(models.Video.created_date.desc())
        .limit(limit)
    )
    videos = result.scalars().all()
    return [
        {
            "id": video.id,
            "title": video.title,
            "category": video.category.name if video.category else "Unknown",
            "created_date": video.created_date,
            "vimeo_url": video.vimeo_url,
            "vimeo_id": video.vimeo_id,
            "thumbnail_url": video.thumbnail_url,
            "like_count": await get_like_count(db, video.id),
            "comment_count": await get_comment_count(db, video.id),
        }
        for video in videos
    ]

# Like Operations
async def add_like(db: AsyncSession, like: schemas.LikeCreate) -> models.Like:
    existing_like = await db.execute(
        select(models.Like)
        .where(models.Like.user_id == like.user_id)
        .where(models.Like.video_id == like.video_id)
    )
    if existing_like.scalars().first():
        raise HTTPException(status_code=400, detail="User has already liked this video")

    db_like = models.Like(**like.dict())
    db.add(db_like)
    await db.commit()
    await db.refresh(db_like)
    return db_like

async def remove_like(db: AsyncSession, user_id: uuid.UUID, video_id: uuid.UUID) -> models.Like:
    result = await db.execute(
        select(models.Like)
        .where(models.Like.user_id == user_id)
        .where(models.Like.video_id == video_id)
    )
    like = result.scalars().first()
    if not like:
        raise HTTPException(status_code=404, detail="Like not found")

    await db.delete(like)
    await db.commit()
    return like

async def get_like_count(db: AsyncSession, video_id: uuid.UUID) -> int:
    result = await db.scalar(
        select(func.count(models.Like.id))
        .where(models.Like.video_id == video_id)
    )
    return result or 0

async def has_user_liked(db: AsyncSession, user_id: uuid.UUID, video_id: uuid.UUID) -> bool:
    result = await db.scalar(
        select(models.Like.id)
        .where(models.Like.user_id == user_id)
        .where(models.Like.video_id == video_id)
    )
    return result is not None

# Comment Operations
async def add_comment(
    db: AsyncSession, 
    comment: schemas.CommentCreate, 
    user_id: uuid.UUID
) -> models.Comment:
    db_comment = models.Comment(
        user_id=user_id,
        video_id=comment.video_id,
        text=comment.text
    )
    db.add(db_comment)
    await db.commit()
    await db.refresh(db_comment)
    return db_comment

async def get_comments(db: AsyncSession, video_id: uuid.UUID) -> List[models.Comment]:
    result = await db.execute(
        select(models.Comment)
        .options(joinedload(models.Comment.user))
        .where(models.Comment.video_id == video_id)
        .order_by(models.Comment.created_at.desc())
    )
    return result.scalars().all()

async def get_comment_count(db: AsyncSession, video_id: uuid.UUID) -> int:
    result = await db.scalar(
        select(func.count(models.Comment.id))
        .where(models.Comment.video_id == video_id)
    )
    return result or 0

async def update_comment(
    db: AsyncSession, 
    comment_id: uuid.UUID, 
    new_text: str, 
    user_id: uuid.UUID
) -> models.Comment:
    result = await db.execute(
        select(models.Comment)
        .where(models.Comment.id == comment_id)
    )
    comment = result.scalars().first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this comment")

    comment.text = new_text
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment

async def delete_comment(
    db: AsyncSession, 
    comment_id: uuid.UUID, 
    current_user_id: uuid.UUID
) -> Dict[str, str]:
    result = await db.execute(
        select(models.Comment)
        .where(models.Comment.id == comment_id)
    )
    comment = result.scalars().first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")

    await db.delete(comment)
    await db.commit()
    return {"detail": "Comment deleted successfully"}

# News Operations
async def create_news(
    db: AsyncSession, 
    news_data: schemas.NewsCreate, 
    author_id: uuid.UUID,
    image_url: Optional[str] = None
) -> models.News:
    db_news = models.News(
        **news_data.dict(exclude={"image"}),
        image_url=image_url,
        author_id=author_id
    )
    db.add(db_news)
    await db.commit()
    await db.refresh(db_news)
    return db_news

async def get_news_list(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    published_only: bool = True,
    author_id: Optional[uuid.UUID] = None
) -> List[models.News]:
    query = select(models.News).options(
        selectinload(models.News.author)
    ).order_by(models.News.created_at.desc())
    
    if published_only:
        query = query.where(models.News.is_published == True)
    if author_id:
        query = query.where(models.News.author_id == author_id)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def get_news_count(
    db: AsyncSession,
    published_only: bool = True
) -> int:
    query = select(func.count(models.News.id))
    if published_only:
        query = query.where(models.News.is_published == True)
    result = await db.scalar(query)
    return result or 0

async def get_news_by_id(
    db: AsyncSession, 
    news_id: uuid.UUID
) -> Optional[models.News]:
    result = await db.execute(
        select(models.News)
        .options(joinedload(models.News.author))
        .where(models.News.id == news_id)
    )
    return result.scalars().first()

async def update_news(
    db: AsyncSession,
    db_news: models.News,
    news_update: schemas.NewsUpdate,
    image_url: Optional[str] = None
) -> models.News:
    update_data = news_update.dict(exclude_unset=True, exclude={"image"})
    
    if image_url is not None:
        update_data["image_url"] = image_url
    
    for field, value in update_data.items():
        setattr(db_news, field, value)
    
    db_news.updated_at = datetime.utcnow()
    db.add(db_news)
    await db.commit()
    await db.refresh(db_news)
    return db_news

async def delete_news(db: AsyncSession, news: models.News) -> None:
    await db.delete(news)
    await db.commit()

async def get_recent_news(db: AsyncSession, limit: int = 5) -> List[models.News]:
    result = await db.execute(
        select(models.News)
        .options(joinedload(models.News.author))
        .where(models.News.is_published == True)
        .order_by(models.News.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()

async def check_news_ownership(
    db: AsyncSession,
    news_id: uuid.UUID,
    user_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(models.News.id)
        .where(and_(
            models.News.id == news_id,
            models.News.author_id == user_id
        ))
    )
    return result.scalar() is not None

async def search_news(
    db: AsyncSession,
    query: str,
    skip: int = 0,
    limit: int = 10
) -> List[models.News]:
    result = await db.execute(
        select(models.News)
        .options(joinedload(models.News.author))
        .where(and_(
            models.News.is_published == True,
            or_(
                models.News.title.ilike(f"%{query}%"),
                models.News.content.ilike(f"%{query}%")
            )
        ))
        .order_by(models.News.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()
async def get_videos_per_category(db: AsyncSession) -> List[Dict[str, Any]]:
    """
    Get video counts for all categories.
    Returns list of dictionaries containing category details and video counts.
    """
    result = await db.execute(
        select(
            models.Category,
            func.count(models.Video.id).label("video_count")
        )
        .join(models.Video, models.Video.category_id == models.Category.id, isouter=True)
        .group_by(models.Category.id)
        .order_by(models.Category.name)
    )
    
    return [
        {
            "category": category,
            "video_count": video_count
        }
        for category, video_count in result.all()
    ]

async def get_category_video_count(db: AsyncSession, category_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """
    Get video count for a specific category.
    Returns dictionary with category details and video count.
    """
    result = await db.execute(
        select(
            models.Category,
            func.count(models.Video.id).label("video_count")
        )
        .join(models.Video, models.Video.category_id == models.Category.id, isouter=True)
        .where(models.Category.id == category_id)
        .group_by(models.Category.id)
    )
    
    row = result.first()
    if not row:
        return None
    
    category, video_count = row
    return {
        "category": category,
        "video_count": video_count
    }

# Enhanced Dashboard Operations
async def get_dashboard_stats(db: AsyncSession) -> Dict[str, Any]:
    """Get comprehensive dashboard statistics"""
    # Basic counts
    total_users = await db.scalar(select(func.count(models.User.id)))
    total_videos = await db.scalar(select(func.count(models.Video.id)))
    total_categories = await db.scalar(select(func.count(models.Category.id)))
    total_news = await get_news_count(db, published_only=True)
    
    # Video counts per category
    categories_with_counts = await get_all_categories_with_video_counts(db)
    
    # Recent activity
    recent_videos = await get_recent_videos(db, limit=5)
    recent_news = await get_recent_news(db, limit=5)
    
    return {
        "total_users": total_users or 0,
        "total_videos": total_videos or 0,
        "total_categories": total_categories or 0,
        "total_news": total_news or 0,
        "categories": [
            {
                "id": item["category"].id,
                "name": item["category"].name,
                "video_count": item["video_count"]
            }
            for item in categories_with_counts
        ],
        "recent_videos": recent_videos,
        "recent_news": recent_news,
        "revenue": 0  # Placeholder for future implementation
    }