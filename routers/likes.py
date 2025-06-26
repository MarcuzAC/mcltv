from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from database import get_db
from auth import get_current_user
import schemas
import crud
from models import User, Video

router = APIRouter(prefix="/likes", tags=["likes"])

@router.post("/", response_model=schemas.LikeResponse, status_code=status.HTTP_201_CREATED)
async def add_like(
    like: schemas.LikeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a like to a video"""
    # Verify video exists
    video_exists = await db.scalar(
        select(Video.id).where(Video.id == like.video_id)
    )
    if not video_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    try:
        # Ensure the like is being created by the authenticated user
        if like.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot like as another user"
            )
            
        return await crud.add_like(db, like)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add like"
        )

@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def remove_like(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a like from a video"""
    try:
        # Verify video exists
        video_exists = await db.scalar(
            select(Video.id).where(Video.id == video_id)
        )
        if not video_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
            
        like = await crud.remove_like(db, current_user.id, video_id)
        if not like:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Like not found"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove like"
        )

@router.get("/{video_id}/count", response_model=int)
async def get_like_count(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get like count for a specific video"""
    try:
        # Verify video exists
        video_exists = await db.scalar(
            select(Video.id).where(Video.id == video_id)
        )
        if not video_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
            
        return await crud.get_like_count(db, video_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get like count"
        )

@router.get("/{video_id}/status", response_model=bool)
async def get_like_status(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check if current user has liked a video"""
    try:
        video_exists = await db.scalar(
            select(Video.id).where(Video.id == video_id)
        )
        if not video_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
            
        return await crud.has_user_liked(db, current_user.id, video_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check like status"
        )