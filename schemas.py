from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional, List
import uuid
from datetime import datetime

# ==== User Schemas ====

class UserBase(BaseModel):
    email: EmailStr
    username: str
    first_name: str
    last_name: str
    phone_number: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    id: uuid.UUID
    is_admin: bool = False
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

# ==== Category Schemas ====

class CategoryBase(BaseModel):
    name: str

class CategoryCreate(CategoryBase):
    pass

class CategoryOut(CategoryBase):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CategoryWithVideoCount(CategoryOut):
    video_count: int

    model_config = ConfigDict(from_attributes=True)

class CategoryResponse(CategoryBase):
    id: uuid.UUID
    video_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# ==== Video Schemas ====

class VideoBase(BaseModel):
    title: str
    category_id: uuid.UUID

class VideoCreate(VideoBase):
    pass

class VideoUpdate(BaseModel):
    title: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    thumbnail_url: Optional[str] = None

class VideoResponse(VideoBase):
    id: uuid.UUID
    created_date: datetime
    vimeo_url: Optional[str] = None
    vimeo_id: Optional[str] = None
    category: Optional[CategoryOut] = None
    category_id: Optional[uuid.UUID] = None
    thumbnail_url: Optional[str] = None
    like_count: int = 0
    comment_count: int = 0

    model_config = ConfigDict(from_attributes=True)

# ==== Token Schema ====

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ==== Like Schemas ====

class LikeBase(BaseModel):
    user_id: uuid.UUID
    video_id: uuid.UUID

class LikeCreate(LikeBase):
    pass

class LikeResponse(LikeBase):
    id: uuid.UUID
    created_at: datetime
    user: Optional[UserResponse] = None
    video: Optional[VideoResponse] = None

    model_config = ConfigDict(from_attributes=True)

# ==== Comment Schemas ====

class CommentBase(BaseModel):
    text: str

class CommentCreate(BaseModel):
    video_id: uuid.UUID
    text: str

class CommentUpdate(BaseModel):
    text: str

class CommentResponse(BaseModel):
    id: uuid.UUID
    text: str
    user_id: uuid.UUID
    video_id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    user: UserResponse
    video: Optional[VideoResponse] = None

    model_config = ConfigDict(from_attributes=True)

# ==== News Schemas ====

class NewsBase(BaseModel):
    title: str
    content: str

class NewsCreate(NewsBase):
    is_published: bool = False

class NewsUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    is_published: Optional[bool] = None

class NewsResponse(NewsBase):
    id: uuid.UUID
    image_url: str
    created_at: datetime
    updated_at: Optional[datetime]
    published_at: Optional[datetime] = None
    author_id: uuid.UUID
    is_published: bool

    model_config = ConfigDict(from_attributes=True)

class NewsListResponse(BaseModel):
    items: List[NewsResponse]
    total: int
    page: int
    size: int

# ==== Dashboard Analytics ====

class UserGrowthData(BaseModel):
    month: str
    count: int

class CategoryDistribution(BaseModel):
    name: str
    count: int

class DashboardStatsResponse(BaseModel):
    total_users: int
    total_videos: int
    total_categories: int
    total_news: int
    published_news: int
    user_growth: List[UserGrowthData]
    video_categories: List[CategoryDistribution]