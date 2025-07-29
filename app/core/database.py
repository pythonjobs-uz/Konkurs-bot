from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, BigInteger, ForeignKey, Index, JSON, Float
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, AsyncGenerator, List, Dict, Any
import enum
import asyncio
import logging
from contextlib import asynccontextmanager
import aiosqlite
import secrets

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
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
    premium_until = Column(DateTime, nullable=True)
    referral_code = Column(String(255), unique=True, nullable=True)
    referred_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    total_referrals = Column(Integer, default=0)
    
    contests = relationship("Contest", back_populates="owner", foreign_keys="Contest.owner_id")
    participations = relationship("Participant", back_populates="user", foreign_keys="Participant.user_id")
    analytics = relationship("UserAnalytics", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    notifications = relationship("Notification", back_populates="user")

class Channel(Base):
    __tablename__ = "channels"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    username = Column(String(255), nullable=True, index=True)
    owner_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    member_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
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
    view_count = Column(Integer, default=0)
    participant_count = Column(Integer, default=0)
    is_premium = Column(Boolean, default=False)
    prize_description = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    owner = relationship("User", back_populates="contests")
    channel = relationship("Channel", back_populates="contests")
    participants = relationship("Participant", back_populates="contest")
    winners = relationship("Winner", back_populates="contest")
    analytics = relationship("ContestAnalytics", back_populates="contest", lazy="dynamic")

class Participant(Base):
    __tablename__ = "participants"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    contest_id = Column(Integer, ForeignKey("contests.id"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    joined_at = Column(DateTime, default=func.now(), index=True)
    is_winner = Column(Boolean, default=False, index=True)
    referral_source = Column(String(255), nullable=True)
    
    contest = relationship("Contest", back_populates="participants")
    user = relationship("User", back_populates="participations", foreign_keys=[user_id])
    
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
    ip_address = Column(String(255), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=func.now(), index=True)
    
    user = relationship("User", back_populates="analytics")
    
    __table_args__ = (
        Index('idx_user_action_time', 'user_id', 'action', 'created_at'),
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

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String(10), default="UZS")
    payment_method = Column(String(255))
    status = Column(String(20), default="pending")
    transaction_id = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    user = relationship("User", back_populates="payments")

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    notification_type = Column(String(20), default="info")
    created_at = Column(DateTime, default=func.now())
    
    user = relationship("User", back_populates="notifications")

@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")

async def close_db():
    await engine.dispose()

class Database:
    def __init__(self, db_path: str = "contest_bot.db"):
        self.db_path = db_path
        self.connection = None
    
    async def init_db(self):
        self.connection = await aiosqlite.connect(self.db_path)
        await self.create_tables()
        logger.info("Database initialized successfully")
    
    async def close(self):
        if self.connection:
            await self.connection.close()
    
    async def create_tables(self):
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT DEFAULT 'uz',
                is_active BOOLEAN DEFAULT 1,
                is_premium BOOLEAN DEFAULT 0,
                is_banned BOOLEAN DEFAULT 0,
                premium_until TIMESTAMP,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                total_referrals INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referred_by) REFERENCES users (id)
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER UNIQUE NOT NULL,
                title TEXT NOT NULL,
                username TEXT,
                owner_id INTEGER NOT NULL,
                member_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                is_verified BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users (id)
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS contests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                image_file_id TEXT,
                participate_button_text TEXT DEFAULT '🤝 Qatnashish',
                winners_count INTEGER DEFAULT 1,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                max_participants INTEGER,
                status TEXT DEFAULT 'pending',
                message_id INTEGER,
                view_count INTEGER DEFAULT 0,
                participant_count INTEGER DEFAULT 0,
                is_premium BOOLEAN DEFAULT 0,
                prize_description TEXT,
                requirements TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users (id),
                FOREIGN KEY (channel_id) REFERENCES channels (channel_id)
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contest_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_winner BOOLEAN DEFAULT 0,
                referral_source TEXT,
                FOREIGN KEY (contest_id) REFERENCES contests (id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(contest_id, user_id)
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS winners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contest_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                prize_claimed BOOLEAN DEFAULT 0,
                announced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contest_id) REFERENCES contests (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                data TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT DEFAULT 'UZS',
                payment_method TEXT,
                status TEXT DEFAULT 'pending',
                transaction_id TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT 0,
                notification_type TEXT DEFAULT 'info',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        await self.connection.commit()
    
    async def create_or_update_user(self, user_id: int, username: str = None, 
                                  first_name: str = None, last_name: str = None, 
                                  language_code: str = "uz") -> Dict[str, Any]:
        cursor = await self.connection.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        existing_user = await cursor.fetchone()
        
        if existing_user:
            await self.connection.execute("""
                UPDATE users SET username = ?, first_name = ?, last_name = ?, 
                language_code = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (username, first_name, last_name, language_code, user_id))
        else:
            referral_code = secrets.token_urlsafe(8)
            await self.connection.execute("""
                INSERT INTO users (id, username, first_name, last_name, language_code, referral_code)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, language_code, referral_code))
        
        await self.connection.commit()
        
        cursor = await self.connection.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        return {}
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        cursor = await self.connection.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        return None
    
    async def get_all_active_users(self) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute(
            "SELECT * FROM users WHERE is_active = 1 AND is_banned = 0"
        )
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def add_channel(self, channel_id: int, title: str, username: str, 
                         owner_id: int, member_count: int = 0) -> bool:
        try:
            await self.connection.execute("""
                INSERT OR REPLACE INTO channels 
                (channel_id, title, username, owner_id, member_count)
                VALUES (?, ?, ?, ?, ?)
            """, (channel_id, title, username, owner_id, member_count))
            await self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            return False
    
    async def get_user_channels(self, user_id: int) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute("""
            SELECT * FROM channels WHERE owner_id = ? AND is_active = 1
            ORDER BY member_count DESC
        """, (user_id,))
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def create_contest(self, owner_id: int, channel_id: int, title: str,
                           description: str, image_file_id: str = None,
                           participate_button_text: str = "🤝 Qatnashish",
                           winners_count: int = 1, start_time: str = None,
                           end_time: str = None, max_participants: int = None,
                           prize_description: str = None, requirements: str = None) -> int:
        cursor = await self.connection.execute("""
            INSERT INTO contests 
            (owner_id, channel_id, title, description, image_file_id, 
             participate_button_text, winners_count, start_time, end_time, 
             max_participants, prize_description, requirements)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (owner_id, channel_id, title, description, image_file_id,
              participate_button_text, winners_count, start_time, end_time, 
              max_participants, prize_description, requirements))
        
        contest_id = cursor.lastrowid
        await self.connection.commit()
        return contest_id
    
    async def get_contest(self, contest_id: int) -> Optional[Dict[str, Any]]:
        cursor = await self.connection.execute("SELECT * FROM contests WHERE id = ?", (contest_id,))
        row = await cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        return None
    
    async def get_user_contests(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute("""
            SELECT * FROM contests WHERE owner_id = ? 
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit))
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def get_active_contests(self) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute("""
            SELECT * FROM contests WHERE status IN ('pending', 'active')
            ORDER BY created_at DESC
        """)
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def update_contest_status(self, contest_id: int, status: str):
        await self.connection.execute(
            "UPDATE contests SET status = ? WHERE id = ?", (status, contest_id)
        )
        await self.connection.commit()
    
    async def set_contest_message_id(self, contest_id: int, message_id: int):
        await self.connection.execute(
            "UPDATE contests SET message_id = ? WHERE id = ?", (message_id, contest_id)
        )
        await self.connection.commit()
    
    async def add_participant(self, contest_id: int, user_id: int, referral_source: str = None) -> bool:
        try:
            await self.connection.execute("""
                INSERT INTO participants (contest_id, user_id, referral_source) VALUES (?, ?, ?)
            """, (contest_id, user_id, referral_source))
            
            await self.connection.execute("""
                UPDATE contests SET participant_count = participant_count + 1 
                WHERE id = ?
            """, (contest_id,))
            
            await self.connection.commit()
            return True
        except Exception:
            return False
    
    async def is_participating(self, contest_id: int, user_id: int) -> bool:
        cursor = await self.connection.execute("""
            SELECT 1 FROM participants WHERE contest_id = ? AND user_id = ?
        """, (contest_id, user_id))
        result = await cursor.fetchone()
        return result is not None
    
    async def get_participants_count(self, contest_id: int) -> int:
        cursor = await self.connection.execute("""
            SELECT COUNT(*) FROM participants WHERE contest_id = ?
        """, (contest_id,))
        result = await cursor.fetchone()
        return result[0] if result else 0
    
    async def get_contest_participants(self, contest_id: int) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute("""
            SELECT u.* FROM users u 
            JOIN participants p ON u.id = p.user_id 
            WHERE p.contest_id = ?
            ORDER BY p.joined_at
        """, (contest_id,))
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def create_winner(self, contest_id: int, user_id: int, position: int):
        await self.connection.execute("""
            INSERT INTO winners (contest_id, user_id, position) VALUES (?, ?, ?)
        """, (contest_id, user_id, position))
        
        await self.connection.execute("""
            UPDATE participants SET is_winner = 1 
            WHERE contest_id = ? AND user_id = ?
        """, (contest_id, user_id))
        
        await self.connection.commit()
    
    async def get_contest_winners(self, contest_id: int) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute("""
            SELECT u.*, w.position FROM users u 
            JOIN winners w ON u.id = w.user_id 
            WHERE w.contest_id = ? ORDER BY w.position
        """, (contest_id,))
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def log_analytics(self, user_id: int = None, action: str = "", 
                          data: str = None, ip_address: str = None, user_agent: str = None):
        await self.connection.execute("""
            INSERT INTO analytics (user_id, action, data, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, action, data, ip_address, user_agent))
        await self.connection.commit()
    
    async def get_analytics_data(self, days: int = 7) -> Dict[str, Any]:
        cursor = await self.connection.execute("""
            SELECT action, COUNT(*) as count FROM analytics 
            WHERE created_at >= datetime('now', '-{} days')
            GROUP BY action ORDER BY count DESC
        """.format(days))
        actions = await cursor.fetchall()
        
        cursor = await self.connection.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count FROM analytics 
            WHERE created_at >= datetime('now', '-{} days')
            GROUP BY DATE(created_at) ORDER BY date
        """.format(days))
        daily_stats = await cursor.fetchall()
        
        return {
            "actions": [{"action": row[0], "count": row[1]} for row in actions],
            "daily_stats": [{"date": row[0], "count": row[1]} for row in daily_stats]
        }
    
    async def create_notification(self, user_id: int, title: str, message: str, 
                                notification_type: str = "info"):
        await self.connection.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type)
            VALUES (?, ?, ?, ?)
        """, (user_id, title, message, notification_type))
        await self.connection.commit()
    
    async def get_user_notifications(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute("""
            SELECT * FROM notifications WHERE user_id = ? 
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit))
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def mark_notification_read(self, notification_id: int):
        await self.connection.execute("""
            UPDATE notifications SET is_read = 1 WHERE id = ?
        """, (notification_id,))
        await self.connection.commit()
    
    async def get_statistics(self) -> Dict[str, int]:
        stats = {}
        
        cursor = await self.connection.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = (await cursor.fetchone())[0]
        
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM users WHERE is_active = 1 AND is_banned = 0"
        )
        stats['active_users'] = (await cursor.fetchone())[0]
        
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM users WHERE is_premium = 1"
        )
        stats['premium_users'] = (await cursor.fetchone())[0]
        
        cursor = await self.connection.execute("SELECT COUNT(*) FROM contests")
        stats['total_contests'] = (await cursor.fetchone())[0]
        
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM contests WHERE status = 'active'"
        )
        stats['active_contests'] = (await cursor.fetchone())[0]
        
        cursor = await self.connection.execute("SELECT COUNT(*) FROM participants")
        stats['total_participants'] = (await cursor.fetchone())[0]
        
        cursor = await self.connection.execute("SELECT COUNT(*) FROM winners")
        stats['total_winners'] = (await cursor.fetchone())[0]
        
        return stats

db = Database()
