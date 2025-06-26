# Initialize routers for the video streaming service
from .users import router as users_router
from .videos import router as videos_router
from .categories import router as categories_router
from .comments import router as comments_router
from .likes import router as likes_router
from .news import router as news_router
from .subscription import router as subscription_router
