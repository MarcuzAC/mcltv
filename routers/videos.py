from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from typing import List
from database import get_db
from auth import get_current_user
import schemas
import crud
import uuid
import tempfile
import os
from sqlalchemy.future import select
from vimeo_client import upload_to_vimeo
from models import User, Video, Category
from sqlalchemy.orm import joinedload
from typing import Optional
from vimeo_client import client

router = APIRouter(prefix="/videos", tags=["videos"])

@router.post("/", response_model=schemas.VideoResponse)
async def create_video(
    title: str = Form(...),
    category_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    temp_path = None
    try:
        # Validate file type
        if file.content_type not in ["video/mp4", "video/quicktime", "video/x-msvideo"]:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Unsupported file type. Only MP4, MOV, and AVI are allowed."
            )

        # Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Upload to Vimeo
        try:
            vimeo_data = upload_to_vimeo(temp_path, title=title)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload video to Vimeo: {str(e)}"
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
                vimeo_id=vimeo_data['vimeo_id']
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save video to database: {str(e)}"
            )

        # ✅ Convert to Pydantic Schema before returning
        return schemas.VideoResponse(
            id=db_video.id,
            title=db_video.title,
            created_date=db_video.created_date,
            vimeo_url=db_video.vimeo_url,
            vimeo_id=db_video.vimeo_id,
            category=db_video.category.name if db_video.category else None  # ✅ Safe access
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

    finally:
        # Cleanup temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                print(f"Failed to delete temp file: {str(e)}")


@router.get("/dashboard/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Retrieve total users, videos, and categories. Revenue is set to 0 by default."""
    total_users = await db.scalar(func.count(User.id))
    total_videos = await db.scalar(func.count(Video.id))
    total_categories = await db.scalar(func.count(Category.id))

    return {
        "total_users": total_users or 0,
        "total_videos": total_videos or 0,
        "total_categories": total_categories or 0,
        "revenue": 0  # Default to 0
    }

@router.get("/recent", response_model=List[schemas.VideoResponse])
async def get_recent_videos(db: AsyncSession = Depends(get_db)):
    """Retrieve the most recent uploaded videos."""
    videos = await crud.get_recent_videos(db)
    return videos

@router.put("/{video_id}", response_model=schemas.VideoResponse)
async def update_video(
    video_id: uuid.UUID,
    video_update: schemas.VideoUpdate,  # Accept JSON request body
    db: AsyncSession = Depends(get_db)
):
    # Fetch video
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
    )

@router.delete("/{video_id}")
async def delete_video(
    video_id: uuid.UUID, 
    db: AsyncSession = Depends(get_db)
):
    video = await crud.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete from Vimeo
    try:
        response = client.delete(f"/videos/{video.vimeo_id}")
        if response.status_code != 204:
            raise HTTPException(status_code=500, detail=f"Vimeo deletion failed: {response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vimeo deletion failed: {str(e)}")
    
    await crud.delete_video(db, video)
    return {"message": "Video deleted successfully"}

@router.get("/", response_model=List[schemas.VideoResponse])
async def read_videos(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    videos = await crud.get_all_videos(db)
    return videos

@router.get("/{video_id}", response_model=schemas.VideoResponse)
async def read_video(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    video = await crud.get_video(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

# Share video endpoint (public)
@router.get("/share/{video_id}", response_class=HTMLResponse)
async def share_video(
    video_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
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