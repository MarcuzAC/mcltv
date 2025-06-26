import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from database import engine, Base
import models
from auth import router as auth_router
from routers import (
    users_router,
    videos_router,
    categories_router,
    likes_router,
    comments_router,
    news_router,
    subscription_router
)

app = FastAPI(
    title="Video API",
    description="A Video streaming application for managing videos based on subscription.",
    version="1.0.0",
    redoc_url="/redoc",
    docs_url="/docs",
)

# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://dashboard-tau-mocha.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_db():
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Debugging: Print all registered routes
    print("\n=== Registered Routes ===")
    for route in app.routes:
        if hasattr(route, "path"):
            methods = ','.join(route.methods) if hasattr(route, "methods") else "???"
            print(f"{methods:7} {route.path}")

# Health Check Endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": app.version}

# Test Endpoint for News Router
@app.get("/news_debug")
async def news_debug():
    return {
        "message": "Direct news debug endpoint",
        "expected_routes": {
            "news_list": "GET /news/",
            "create_news": "POST /news/",
            "get_news": "GET /news/{news_id}",
            "latest_news": "GET /news/latest/",
            "search_news": "GET /news/search/"
        }
    }

# Include all routers with explicit prefixes
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(videos_router, prefix="/videos", tags=["videos"])
app.include_router(categories_router, prefix="/categories", tags=["categories"])
app.include_router(likes_router, prefix="/likes", tags=["likes"])
app.include_router(comments_router, prefix="/comments", tags=["comments"])
app.include_router(news_router, prefix="/news", tags=["news"])
app.include_router(subscription_router, prefix="/subscription", tags=["subscription"])

# Root redirect
@app.get("/")
async def root():
    return RedirectResponse(url="/redoc")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=True)