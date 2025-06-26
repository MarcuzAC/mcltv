from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={
        "statement_cache_size": 0,
        "max_cacheable_statement_size": 0,
        "prepared_statement_cache_size": 0
    },
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True
)

async_session = sessionmaker(
    bind=engine, 
    class_=AsyncSession,
    expire_on_commit=False
)
Base = declarative_base()

async def get_db():
    async with async_session() as session:
        yield session