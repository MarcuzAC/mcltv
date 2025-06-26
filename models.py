import uuid
import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, Float
from sqlalchemy.dialects.postgresql import UUID
from database import Base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    username = Column(String(50), unique=True, index=True)
    phone_number = Column(String(20))
    email = Column(String(100), unique=True, index=True)
    is_admin = Column(Boolean, default=False)
    hashed_password = Column(String)
    reset_token = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    is_subscribed = Column(Boolean, default=False)
    subscription_expiry = Column(DateTime, nullable=True)  # Nullable to allow non-s

    # Relationships
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    news = relationship("News", back_populates="author")

    def is_subscription_active(self):
        """Check if the user's subscription is active."""
        if not self.is_subscribed or not self.subscription_expiry:
            return False
        return self.subscription_expiry > datetime.datetime.utcnow()

class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, index=True)

    videos = relationship("Video", back_populates="category", cascade="all, delete-orphan")

class Video(Base):
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(100), nullable=False)
    thumbnail_url = Column(String)
    created_date = Column(DateTime, server_default=func.now(), index=True)  # Changed to server_default
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    vimeo_url = Column(String)
    vimeo_id = Column(String)

    category = relationship("Category", back_populates="videos")
    
    # Relationships with cascade delete
    likes = relationship("Like", back_populates="video", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="video", cascade="all, delete-orphan")

class Like(Base):
    __tablename__ = "likes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="likes")
    video = relationship("Video", back_populates="likes")

    # Ensure a user can like a video only once
    __table_args__ = (
        UniqueConstraint('user_id', 'video_id', name='unique_user_video_like'),
    )

class News(Base):
    __tablename__ = "news"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    # image_url = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, onupdate=func.now())
    is_published = Column(Boolean, default=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Relationship
    author = relationship("User", back_populates="news")

class Comment(Base):
    __tablename__ = "comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="comments")
    video = relationship("Video", back_populates="comments")

class Revenue(Base):
    __tablename__ = "revenue"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amount = Column(Float, nullable=False)  # Changed from db.Float to Float
    date = Column(DateTime, server_default=func.now(), index=True)
    source = Column(String(50))  # e.g., "subscription", "advertisement", "sponsorship"
    description = Column(String(200))
# Add this to your models.py
class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    currency = Column(String(3), default="MWK")
    duration_days = Column(Integer, nullable=False)  # Duration in days
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationship to track which users have this plan (optional)
    # subscriptions = relationship("UserSubscription", back_populates="plan")