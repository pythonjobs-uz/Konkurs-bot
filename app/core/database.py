from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, BigInteger, ForeignKey, Index, JSON, Float
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
import enum

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=3600
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class ContestStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    ENDED = "ended"
    CANCELLED = "cancelled"

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
    last_activity = Column(DateTime, default=func.now(), index=True)
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    contests = relationship("Contest", back_populates="owner")
    participations = relationship("Participant", back_populates="user")
    analytics = relationship("UserAnalytics", back_populates="user")

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
    
    owner = relationship("User")
    contests = relationship("Contest", back_populates="channel")

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
    created_at = Column(DateTime, default=func.now(), index=True)
    
    owner = relationship("User", back_populates="contests")
    channel = relationship("Channel", back_populates="contests")
    participants = relationship("Participant", back_populates="contest")
    winners = relationship("Winner", back_populates="contest")
    analytics = relationship("ContestAnalytics", back_populates="contest")

class Participant(Base):
    __tablename__ = "participants"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    contest_id = Column(Integer, ForeignKey("contests.id"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    joined_at = Column(DateTime, default=func.now(), index=True)
    referrer_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    
    contest = relationship("Contest", back_populates="participants")
    user = relationship("User", back_populates="participations")
    
    __table_args__ = (
        Index('idx_contest_user', 'contest_id', 'user_id', unique=True),
    )

class Winner(Base):
    __tablename__ = "winners"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    contest_id = Column(Integer, ForeignKey("contests.id"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    prize_claimed = Column(Boolean, default=False)
    announced_at = Column(DateTime, default=func.now())
    
    contest = relationship("Contest", back_populates="winners")
    user = relationship("User")

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

class ContestAnalytics(Base):
    __tablename__ = "contest_analytics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    contest_id = Column(Integer, ForeignKey("contests.id"), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=func.now(), index=True)
    
    contest = relationship("Contest", back_populates="analytics")

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
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=func.now())
    sent_at = Column(DateTime, nullable=True)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
