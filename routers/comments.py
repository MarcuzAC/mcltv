from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from database import get_db
from auth import get_current_user
import models
import schemas
import crud
from models import User, Video, Comment

router = APIRouter(prefix="/comments", tags=["comments"])

@router.post("/", response_model=schemas.CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    comment: schemas.CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a new comment to a video"""
    # Check if video exists
    video_exists = await db.scalar(
        select(models.Video.id).where(models.Video.id == comment.video_id)
    )
    if not video_exists:
        raise HTTPException(status_code=404, detail="Video not found")
    
    try:
        db_comment = await crud.add_comment(
            db=db, 
            comment=comment, 
            user_id=current_user.id
        )
        return schemas.CommentResponse.model_validate(db_comment)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{video_id}", response_model=List[schemas.CommentResponse])
async def get_comments(
    video_id: uuid.UUID, 
    db: AsyncSession = Depends(get_db)
):
    """Get all comments for a specific video"""
    video_exists = await db.scalar(
        select(models.Video.id).where(models.Video.id == video_id)
    )
    if not video_exists:
        raise HTTPException(status_code=404, detail="Video not found")
    
    try:
        comments = await crud.get_comments(db=db, video_id=video_id)
        return [
            schemas.CommentResponse(
                id=comment.id,
                text=comment.text,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                user=schemas.UserBase(
                    id=comment.user.id,
                    username=comment.user.username,
                    avatar_url=comment.user.avatar_url
                )
            )
            for comment in comments
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve comments"
        )

@router.put("/{comment_id}", response_model=schemas.CommentResponse)
async def update_comment(
    comment_id: uuid.UUID,
    updated_data: schemas.CommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing comment"""
    try:
        updated_comment = await crud.update_comment(
            db=db,
            comment_id=comment_id,
            new_text=updated_data.text,
            user_id=current_user.id
        )
        return schemas.CommentResponse.model_validate(updated_comment)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in str(e).lower() 
            else status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update comment"
        )

@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a comment"""
    try:
        await crud.delete_comment(
            db=db,
            comment_id=comment_id,
            current_user_id=current_user.id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in str(e).lower() 
            else status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete comment"
        )