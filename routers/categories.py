from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
import uuid

from database import get_db
from models import Category, Video
from schemas import CategoryCreate, CategoryOut
from crud import get_videos_per_category

router = APIRouter(prefix="/categories", tags=["categories"])

@router.post("/", response_model=CategoryOut, status_code=201)
async def create_category(
    category: CategoryCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new category"""
    # Check if category with this name already exists
    existing = await db.execute(
        select(Category)
        .where(func.lower(Category.name) == func.lower(category.name))
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="Category with this name already exists"
        )
    
    db_category = Category(**category.dict())
    db.add(db_category)
    await db.commit()
    await db.refresh(db_category)
    return db_category

@router.get("/", response_model=List[CategoryOut])
async def get_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """Get all categories with pagination"""
    result = await db.execute(
        select(Category)
        .order_by(Category.name)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

@router.get("/{category_id}", response_model=CategoryOut)
async def get_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a single category by ID"""
    category = await db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@router.get("/by-name/{name}", response_model=CategoryOut)
async def get_category_by_name(
    name: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a category by name (case-insensitive)"""
    result = await db.execute(
        select(Category)
        .where(func.lower(Category.name) == func.lower(name))
    )
    category = result.scalars().first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@router.put("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: uuid.UUID,
    category: CategoryCreate,
    db: AsyncSession = Depends(get_db)
):
    """Update a category"""
    db_category = await db.get(Category, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check if another category already has this name
    existing = await db.execute(
        select(Category)
        .where(
            func.lower(Category.name) == func.lower(category.name),
            Category.id != category_id
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="Another category with this name already exists"
        )

    db_category.name = category.name
    await db.commit()
    await db.refresh(db_category)
    return db_category

@router.delete("/{category_id}")
async def delete_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a category"""
    category = await db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check if category has associated videos
    has_videos = await db.scalar(
        select(func.count(Video.id))
        .where(Video.category_id == category_id)
    )
    if has_videos:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete category with associated videos"
        )

    await db.delete(category)
    await db.commit()
    return {"message": "Category deleted successfully"}

@router.get("/video-counts/", response_model=List[dict])
async def get_category_video_counts(
    db: AsyncSession = Depends(get_db)
):
    """
    Get video counts for all categories.
    Returns list of dictionaries with category details and video counts.
    """
    return await get_videos_per_category(db)

@router.get("/{category_id}/video-count", response_model=dict)
async def get_single_category_video_count(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get video count for a specific category.
    Returns dictionary with category details and video count.
    """
    category = await db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    video_count = await db.scalar(
        select(func.count(Video.id))
        .where(Video.category_id == category_id)
    )

    return {
        "category_id": category.id,
        "category_name": category.name,
        "video_count": video_count or 0
    }