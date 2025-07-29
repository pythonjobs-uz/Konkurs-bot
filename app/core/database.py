from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, BigInteger, ForeignKey, Index, JSON, Float
from sqlalchemy.sql import func
from sqlalchemy.pool import StaticPool
from datetime import datetime
from typing import Optional, AsyncGenerator
import enum
import asyncio
import logging
from contextlib import asynccontextmanager

from app.core.config import settings

logger = logging.getLogger(__name__)

def create_database_engine():
    engine_kwargs = {
        "echo": settings.DEBUG,
        "pool_pre_ping": True,
    }
    
    if settings.is_sqlite:
        engine_kwargs.update({
            "poolclass": StaticPool,
            "connect_args": {
                "check_same_thread": False,
                "timeout": 20
            }
        })
    elif settings.is_postgresql:
        engine_kwargs.update({
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_recycle": settings.DB_POOL_RECYCLE,
            "pool_reset_on_return": "commit"
        })
    
    return create_async_engine(settings.DATABASE_URL, **engine_kwargs)

engine = create_database_engine()
async_session = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=True,
    autocommit=False
)

class Base(DeclarativeBase):
    pass

class ContestStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    ENDED = "ended"
    CANCELLED = "cancelled"

class BroadcastStatus(enum.Enum):
    PENDING = "pending"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"

class User(Base):
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True)
    username = Column(String(255), nullable=True, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    language_code = Column(String(10), default="uz", index=True)
    is_active = Column(Boolean, default=True, index=True)
    is_admin = Column(Boolean, default=False, index=True)
    is_premium = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False, index=True)
    last_activity = Column(DateTime, default=func.now(), index=True)
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Fixed relationships with explicit foreign_keys
    contests = relationship("Contest", back_populates="owner", foreign_keys="Contest.owner_id")
    participations = relationship("Participant", back_populates="user", foreign_keys="Participant.user_id")
    analytics = relationship("UserAnalytics", back_populates="user", foreign_keys="UserAnalytics.user_id")

class Channel(Base):
    __tablename__ = "channels"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    username = Column(String(255), nullable=True, index=True)
    owner_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    member_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    owner = relationship("User")
    contests = relationship("Contest", back_populates="channel", lazy="dynamic")

class Contest(Base):
    __tablename__ = "contests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    channel_id = Column(BigInteger, ForeignKey("channels.channel_id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    image_file_id = Column(String(255), nullable=True)
    participate_button_text = Column(String(100), default="🤝 Qatnashish")
    winners_count = Column(Integer, default=1)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=True, index=True)
    max_participants = Column(Integer, nullable=True)
    status = Column(String(20), default="pending", index=True)
    message_id = Column(BigInteger, nullable=True)
    prize_description = Column(Text, nullable=True)
    requirements = Column(JSON, nullable=True)
    view_count = Column(Integer, default=0)
    participant_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    owner = relationship("User", back_populates="contests")
    channel = relationship("Channel", back_populates="contests")
    participants = relationship("Participant", back_populates="contest", lazy="dynamic")
    winners = relationship("Winner", back_populates="contest", lazy="dynamic")
    analytics = relationship("ContestAnalytics", back_populates="contest", lazy="dynamic")

class Participant(Base):
    __tablename__ = "participants"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    contest_id = Column(Integer, ForeignKey("contests.id"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    joined_at = Column(DateTime, default=func.now(), index=True)
    referrer_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    is_winner = Column(Boolean, default=False, index=True)
    
    # Fixed relationships with explicit foreign_keys
    contest = relationship("Contest", back_populates="participants")
    user = relationship("User", back_populates="participations", foreign_keys=[user_id])
    referrer = relationship("User", foreign_keys=[referrer_id])
    
    __table_args__ = (
        Index('idx_contest_user', 'contest_id', 'user_id', unique=True),
        Index('idx_contest_joined', 'contest_id', 'joined_at'),
    )

class Winner(Base):
    __tablename__ = "winners"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    contest_id = Column(Integer, ForeignKey("contests.id"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    prize_claimed = Column(Boolean, default=False)
    prize_description = Column(Text, nullable=True)
    announced_at = Column(DateTime, default=func.now())
    
    contest = relationship("Contest", back_populates="winners")
    user = relationship("User", foreign_keys=[user_id])
    
    __table_args__ = (
        Index('idx_contest_position', 'contest_id', 'position', unique=True),
    )

class ForceSubChannel(Base):
    __tablename__ = "force_sub_channels"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    username = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())

class UserAnalytics(Base):
    __tablename__ = "user_analytics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=func.now(), index=True)
    
    user = relationship("User", back_populates="analytics")
    
    __table_args__ = (
        Index('idx_user_action_time', 'user_id', 'action', 'timestamp'),
    )

class ContestAnalytics(Base):
    __tablename__ = "contest_analytics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    contest_id = Column(Integer, ForeignKey("contests.id"), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=func.now(), index=True)
    
    contest = relationship("Contest", back_populates="analytics")
    
    __table_args__ = (
        Index('idx_contest_metric_time', 'contest_id', 'metric_name', 'timestamp'),
    )

class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    message_text = Column(Text, nullable=True)
    image_file_id = Column(String(255), nullable=True)
    button_text = Column(String(100), nullable=True)
    button_url = Column(String(500), nullable=True)
    target_users = Column(JSON, nullable=True)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    status = Column(String(20), default="pending", index=True)
    created_at = Column(DateTime, default=func.now())
    sent_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

class DatabaseManager:
    def __init__(self):
        self.engine = engine
        self.session_factory = async_session
        self._initialized = False
    
    async def initialize(self, max_retries: int = 5, retry_delay: float = 1.0):
        if self._initialized:
            return
        
        for attempt in range(max_retries):
            try:
                await self.create_tables()
                await self.test_connection()
                self._initialized = True
                logger.info("Database initialized successfully")
                return
            except Exception as e:
                logger.error(f"Database initialization attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                else:
                    raise
    
    async def create_tables(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def test_connection(self):
        async with self.session_factory() as session:
            await session.execute("SELECT 1")
    
    async def close(self):
        await self.engine.dispose()
        logger.info("Database connections closed")

db_manager = DatabaseManager()

@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if not db_manager._initialized:
        await db_manager.initialize()
    
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    await db_manager.initialize()

async def close_db():
    await db_manager.close()
