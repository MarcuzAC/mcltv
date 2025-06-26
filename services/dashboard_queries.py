from sqlalchemy import select, func
from datetime import datetime, timedelta

from models import User, Video, Category, News, Revenue

async def get_dashboard_stats(db):
    # Basic counts
    total_users = await db.scalar(select(func.count(User.id)))
    total_videos = await db.scalar(select(func.count(Video.id)))
    total_categories = await db.scalar(select(func.count(Category.id)))
    total_news = await db.scalar(select(func.count(News.id)))
    total_revenue = await db.scalar(select(func.sum(Revenue.amount))) or 0
    
    # User growth (last 6 months)
    user_growth = await db.execute(
        select(
            func.date_trunc('month', User.created_at).label('month'),
            func.count(User.id).label('count')
        )
        .filter(User.created_at >= datetime.utcnow() - timedelta(days=180))
        .group_by(func.date_trunc('month', User.created_at))
    )
    
    # Video categories
    video_categories = await db.execute(
        select(
            Category.name,
            func.count(Video.id).label('count')
        )
        .join(Video, isouter=True)
        .group_by(Category.name)
    )
    
    # Revenue trends (last 4 quarters)
    revenue_trends = await db.execute(
        select(
            func.date_trunc('quarter', Revenue.date).label('quarter'),
            func.sum(Revenue.amount).label('amount')
        )
        .group_by(func.date_trunc('quarter', Revenue.date))
    )
    
    return {
        "counts": {
            "users": total_users,
            "videos": total_videos,
            "categories": total_categories,
            "news": total_news,
            "revenue": total_revenue
        },
        "user_growth": [
            {"month": m.strftime("%b %Y"), "count": c} 
            for m, c in user_growth
        ],
        "video_categories": [
            {"name": n, "count": c} 
            for n, c in video_categories
        ],
        "revenue_trends": [
            {"quarter": f"Q{(q.month-1)//3 + 1} {q.year}", "amount": a} 
            for q, a in revenue_trends
        ]
    }