import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from typing import List
import uuid

from database import get_db
from auth import get_current_user
import models
import schemas
import crud
from models import User, Video

# Set up logging
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/likes", tags=["likes"])

# In routers/likes.py
# In routers/likes.py
@router.post("/", response_model=schemas.LikeResponse, status_code=status.HTTP_201_CREATED)
async def add_like(
    like: schemas.LikeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a like to a video"""
    try:
        # Verify video exists
        video_exists = await db.scalar(
            select(Video.id).where(Video.id == like.video_id)
        )
        if not video_exists:
            error_msg = f"Video not found: {like.video_id}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        
        # Check if user already liked the video with all relationships loaded
        existing_like = await db.execute(
            select(models.Like)
            .options(
                joinedload(models.Like.user),
                joinedload(models.Like.video).joinedload(models.Video.category)
            )
            .where(models.Like.user_id == current_user.id)
            .where(models.Like.video_id == like.video_id)
        )
        existing_like = existing_like.scalars().first()
        
        if existing_like:
            return existing_like

        # Create new like
        like_data = schemas.LikeCreateWithUser(
            video_id=like.video_id,
            user_id=current_user.id
        )
        new_like = await crud.add_like(db, like_data)
        
        # Refresh with all relationships
        result = await db.execute(
            select(models.Like)
            .options(
                joinedload(models.Like.user),
                joinedload(models.Like.video).joinedload(models.Video.category)
            )
            .where(models.Like.id == new_like.id)
        )
        return result.scalars().first()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error adding like for video {like.video_id} by user {current_user.id}: {str(e)}", 
            exc_info=True
        )
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
            error_msg = f"Video not found while removing like: {video_id}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
            
        like = await crud.remove_like(db, current_user.id, video_id)
        if not like:
            error_msg = f"Like not found for video {video_id} by user {current_user.id}"
            logger.warning(error_msg)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Like not found"
            )
            
    except ValueError as e:
        logger.error(f"Validation error while removing like: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error removing like for video {video_id} by user {current_user.id}: {str(e)}",
            exc_info=True
        )
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
            error_msg = f"Video not found while getting like count: {video_id}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
            
        return await crud.get_like_count(db, video_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error getting like count for video {video_id}: {str(e)}",
            exc_info=True
        )
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
            error_msg = f"Video not found while checking like status: {video_id}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
            
        return await crud.has_user_liked(db, current_user.id, video_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error checking like status for video {video_id} by user {current_user.id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check like status"
        )