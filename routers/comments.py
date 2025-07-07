from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
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
    video_exists = await db.scalar(
        select(models.Video.id).where(models.Video.id == comment.video_id)
    )
    if not video_exists:
        raise HTTPException(status_code=404, detail="Video not found")
    
    try:
        # Add comment
        db_comment = await crud.add_comment(
            db=db, 
            comment=comment, 
            user_id=current_user.id
        )

        # Re-fetch comment with joined relationships
        result = await db.execute(
            select(models.Comment)
            .options(
                joinedload(models.Comment.user),
                joinedload(models.Comment.video).joinedload(models.Video.category)
            )
            .where(models.Comment.id == db_comment.id)
        )
        comment_with_relations = result.scalars().first()
        return schemas.CommentResponse.model_validate(comment_with_relations)

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
        result = await db.execute(
            select(models.Comment)
            .options(
                joinedload(models.Comment.user),
                joinedload(models.Comment.video).joinedload(models.Video.category)
            )
            .where(models.Comment.video_id == video_id)
            .order_by(models.Comment.created_at.desc())
        )
        comments = result.scalars().all()

        return [schemas.CommentResponse.model_validate(comment) for comment in comments]

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

        # Re-fetch with relations
        result = await db.execute(
            select(models.Comment)
            .options(
                joinedload(models.Comment.user),
                joinedload(models.Comment.video).joinedload(models.Video.category)
            )
            .where(models.Comment.id == updated_comment.id)
        )
        comment_with_relations = result.scalars().first()

        return schemas.CommentResponse.model_validate(comment_with_relations)

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
