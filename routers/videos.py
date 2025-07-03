import uuid
import datetime
import os
import tempfile
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, Request, Response, 
    UploadFile, File, Form, status
)
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, func, select
from sqlalchemy.orm import joinedload

from database import get_db
from auth import get_current_user, get_current_subscribed_user
import models
import schemas
import crud
from models import User, Video, Category, Like, Comment, News
from vimeo_client import upload_to_vimeo, client

router = APIRouter(prefix="/videos", tags=["videos"])

# Create a new video with thumbnail
@router.post("/", response_model=schemas.VideoResponse)
async def create_video(
    title: str = Form(...),
    category_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    thumbnail: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """Create a new video entry with optional thumbnail (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can upload videos"
        )

    temp_path = None
    thumbnail_path = None
    try:
        # Validate video file type
        if file.content_type not in ["video/mp4", "video/quicktime", "video/x-msvideo"]:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Unsupported file type. Only MP4, MOV, and AVI are allowed."
            )

        # Save video temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Save thumbnail temp file (if provided)
        if thumbnail:
            if thumbnail.content_type not in ["image/jpeg", "image/png", "image/gif"]:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Unsupported thumbnail type. Only JPEG, PNG, and GIF are allowed."
                )
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(thumbnail.filename)[1]) as thumbnail_temp_file:
                thumbnail_content = await thumbnail.read()
                thumbnail_temp_file.write(thumbnail_content)
                thumbnail_path = thumbnail_temp_file.name

        # Upload video to Vimeo
        try:
            vimeo_data = upload_to_vimeo(temp_path, title=title)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload video to Vimeo: {str(e)}"
            )

        # Upload thumbnail to a storage service
        thumbnail_url = None
        if thumbnail_path:
            try:
                thumbnail_filename = f"{uuid.uuid4()}{os.path.splitext(thumbnail.filename)[1]}"
                thumbnail_dir = "thumbnails"
                os.makedirs(thumbnail_dir, exist_ok=True)
                thumbnail_url = f"/{thumbnail_dir}/{thumbnail_filename}"
                os.rename(thumbnail_path, os.path.join(thumbnail_dir, thumbnail_filename))
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload thumbnail: {str(e)}"
                )

        # Create video entry
        video_data = schemas.VideoCreate(
            title=title,
            category_id=category_id
        )
        
        # Save to database
        try:
            db_video = await crud.create_video(
                db=db,
                video=video_data,
                vimeo_url=vimeo_data['vimeo_url'],
                vimeo_id=vimeo_data['vimeo_id'],
                thumbnail_url=thumbnail_url
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save video to database: {str(e)}"
            )

        return schemas.VideoResponse(
            id=db_video.id,
            title=db_video.title,
            created_date=db_video.created_date,
            vimeo_url=db_video.vimeo_url,
            vimeo_id=db_video.vimeo_id,
            category=db_video.category.name if db_video.category else None,
            thumbnail_url=db_video.thumbnail_url
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        # Cleanup temp files
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                print(f"Failed to delete video temp file: {str(e)}")
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                os.remove(thumbnail_path)
            except Exception as e:
                print(f"Failed to delete thumbnail temp file: {str(e)}")

# Get comprehensive dashboard stats
@router.get("/dashboard/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """Get comprehensive dashboard statistics (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can view dashboard stats"
        )

    try:
        # Get basic counts
        total_users = await db.scalar(select(func.count(User.id)))
        total_videos = await db.scalar(select(func.count(Video.id)))
        total_categories = await db.scalar(select(func.count(Category.id)))
        total_news = await db.scalar(select(func.count(News.id)))
        
        # Get user growth data (last 6 months)
        six_months_ago = datetime.datetime.utcnow() - datetime.timedelta(days=180)
        try:
            user_growth = await db.execute(
                select(
                    func.date_trunc('month', User.created_at).label('month'),
                    func.count(User.id).label('count')
                )
                .filter(User.created_at >= six_months_ago)
                .group_by(func.date_trunc('month', User.created_at))
            )
            user_growth_data = user_growth.all()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get user growth data: {str(e)}"
            )
        
        # Get video categories distribution
        video_categories = await db.execute(
            select(
                Category.name,
                func.count(Video.id).label('count')
            )
            .join(Video, Category.id == Video.category_id, isouter=True)
            .group_by(Category.name))
        video_categories_data = video_categories.all()
        
        # Get recent videos (last 5)
        recent_videos = await db.execute(
            select(Video)
            .order_by(Video.created_date.desc())
            .limit(5)
        )
        recent_videos_data = recent_videos.scalars().all()
        
        return {
            "total_users": total_users or 0,
            "total_videos": total_videos or 0,
            "total_categories": total_categories or 0,
            "total_news": total_news or 0,
            "total_revenue": 0,  # Placeholder - implement your revenue logic
            "user_growth": {
                "months": [month.strftime("%b %Y") for month, count in user_growth_data],
                "counts": [count for month, count in user_growth_data]
            },
            "video_categories": {
                "names": [name for name, count in video_categories_data],
                "counts": [count for name, count in video_categories_data]
            },
            "recent_videos": [
                {
                    "id": video.id,
                    "title": video.title,
                    "created_date": video.created_date,
                    "category": video.category.name if video.category else None,
                    "thumbnail_url": video.thumbnail_url
                }
                for video in recent_videos_data
            ]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load dashboard stats: {str(e)}"
        )

# Get recent videos
@router.get("/recent", response_model=List[schemas.VideoResponse])
async def get_recent_videos(
    limit: int = Query(5, description="Number of recent videos to fetch"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_subscribed_user)
):
    """Get most recently added videos (subscribers only)"""
    result = await db.execute(
        select(Video)
        .options(joinedload(Video.category))
        .order_by(Video.created_date.desc())
        .limit(limit)
    )
    videos = result.scalars().all()
    
    return [
        schemas.VideoResponse(
            id=video.id,
            title=video.title,
            created_date=video.created_date,
            vimeo_url=video.vimeo_url,
            vimeo_id=video.vimeo_id,
            category=video.category.name if video.category else None,
            thumbnail_url=video.thumbnail_url
        )
        for video in videos
    ]

# Update a video
@router.put("/{video_id}", response_model=schemas.VideoResponse)
async def update_video(
    video_id: uuid.UUID,
    video_update: schemas.VideoUpdate,
    thumbnail: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """Update video details and/or thumbnail (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can update videos"
        )

    result = await db.execute(
        select(Video).options(joinedload(Video.category)).filter(Video.id == video_id)
    )
    video = result.scalars().first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    update_data = video_update.model_dump(exclude_unset=True)

    if "category_id" in update_data and update_data["category_id"] is not None:
        category_exists = await db.execute(select(Category).filter(Category.id == update_data["category_id"]))
        if not category_exists.scalars().first():
            raise HTTPException(status_code=400, detail="Invalid category_id.")

    # Update thumbnail (if provided)
    if thumbnail:
        if thumbnail.content_type not in ["image/jpeg", "image/png", "image/gif"]:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Unsupported thumbnail type. Only JPEG, PNG, and GIF are allowed."
            )

        try:
            # First remove old thumbnail if it exists
            if video.thumbnail_url:
                old_thumbnail_path = os.path.join("thumbnails", os.path.basename(video.thumbnail_url))
                if os.path.exists(old_thumbnail_path):
                    os.remove(old_thumbnail_path)

            # Save new thumbnail
            thumbnail_filename = f"{uuid.uuid4()}{os.path.splitext(thumbnail.filename)[1]}"
            thumbnail_dir = "thumbnails"
            os.makedirs(thumbnail_dir, exist_ok=True)
            thumbnail_url = f"/{thumbnail_dir}/{thumbnail_filename}"
            with open(os.path.join(thumbnail_dir, thumbnail_filename), "wb") as buffer:
                buffer.write(await thumbnail.read())
            video.thumbnail_url = thumbnail_url
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload thumbnail: {str(e)}"
            )

    # Apply updates
    for key, value in update_data.items():
        setattr(video, key, value)

    db.add(video)
    await db.commit()
    await db.refresh(video)

    return schemas.VideoResponse(
        id=video.id,
        title=video.title,
        created_date=video.created_date,
        vimeo_url=video.vimeo_url,
        vimeo_id=video.vimeo_id,
        category=video.category.name if video.category else None,
        thumbnail_url=video.thumbnail_url
    )

# Delete a video
@router.delete("/{video_id}")
async def delete_video(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """Delete a video and its associated resources (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can delete videos"
        )

    try:
        # First get the video to check existence and get Vimeo ID
        result = await db.execute(
            select(models.Video).filter(models.Video.id == video_id)
        )
        video = result.scalars().first()
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        # Delete video from Vimeo
        if video.vimeo_id:
            try:
                client.delete_video(video.vimeo_id)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete video from Vimeo: {str(e)}"
                )

        # Delete thumbnail file if it exists
        if video.thumbnail_url:
            try:
                thumbnail_path = os.path.join("thumbnails", os.path.basename(video.thumbnail_url))
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
            except Exception as e:
                print(f"Failed to delete thumbnail file: {str(e)}")

        # Delete video from database (this will cascade to likes and comments)
        await db.delete(video)
        await db.commit()
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/search", response_model=List[schemas.VideoResponse])
async def search_videos(
    query: str = Query(..., min_length=1, max_length=100, description="Search term for video titles"),
    category_id: Optional[uuid.UUID] = Query(None, description="Optional category filter"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=1000, description="Pagination limit"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_subscribed_user)
):
    """Search videos by title with optional category filtering (subscribers only)"""
    try:
        stmt = (
            select(Video)
            .options(joinedload(Video.category))
            .filter(Video.title.ilike(f"%{query}%"))
        )

        if category_id:
            stmt = stmt.filter(Video.category_id == category_id)

        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        videos = result.scalars().all()

        return [
            schemas.VideoResponse(
                id=video.id,
                title=video.title,
                created_date=video.created_date,
                vimeo_url=video.vimeo_url,
                vimeo_id=video.vimeo_id,
                category=video.category.name if video.category else None,
                thumbnail_url=video.thumbnail_url
            )
            for video in videos
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )

# Get all videos
@router.get("/", response_model=List[schemas.VideoResponse])
async def read_videos(
    skip: int = 0,
    limit: int = 100,
    category_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_subscribed_user)
):
    """Get paginated list of all videos with optional category filter (subscribers only)"""
    videos = await crud.get_all_videos(db, skip=skip, limit=limit, category_id=category_id)
    return videos

# Get video by ID
@router.get("/{video_id}", response_model=schemas.VideoResponse)
async def read_video(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_subscribed_user)
):
    """Get video details by ID including like and comment counts (subscribers only)"""
    result = await db.execute(
        select(Video)
        .options(joinedload(Video.category), joinedload(Video.likes), joinedload(Video.comments))
        .filter(Video.id == video_id)
    )
    video = result.scalars().first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return schemas.VideoResponse(
        id=video.id,
        title=video.title,
        created_date=video.created_date,
        vimeo_url=video.vimeo_url,
        vimeo_id=video.vimeo_id,
        category=video.category.name if video.category else None,
        thumbnail_url=video.thumbnail_url,
        likes_count=len(video.likes),
        comments_count=len(video.comments)
    )

# Share video endpoint
@router.get("/share/{video_id}", response_class=HTMLResponse)
async def share_video(
    video_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Generate shareable HTML page for a video (public)"""
    result = await db.execute(
        select(Video).filter(Video.id == video_id)
    )
    video = result.scalars().first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    user_agent = request.headers.get("user-agent", "").lower()
    is_android = "android" in user_agent
    apk_download_url = "https://www.mediafire.com/file/uj2s3y6nmkkze12/mlctv.apk/file"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta property="og:title" content="{video.title}">
        <meta property="og:description" content="Watch this video in MCL TV app.">
        <meta property="og:image" content="{request.base_url}{video.thumbnail_url.lstrip('/') if video.thumbnail_url else ''}">
        <meta property="og:url" content="{request.url}">
        <script>
            function redirectToApp() {{
                window.location.href = 'mlctv://video/{video_id}';
                setTimeout(function() {{
                    window.location.href = '{apk_download_url}';
                }}, 500);
            }}
            {"window.onload = redirectToApp;" if is_android else ""}
        </script>
    </head>
    <body>
        <div style="text-align: center; padding: 50px;">
            <h1>{video.title}</h1>
            {"<p>For the best experience, please install our Android app.</p>" if is_android else "<p>This content is available on Android devices only.</p>"}
            {"<a href='{apk_download_url}'><button style='padding: 10px 20px; background-color: #4285F4; color: white; border: none; border-radius: 5px; font-size: 16px;'>Download Android App</button></a>" if is_android else ""}
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)