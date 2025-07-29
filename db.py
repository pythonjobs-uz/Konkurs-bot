import aiosqlite
import asyncio
from datetime import datetime
from typing import List, Optional
from models import User, Contest, Participant, Winner, Admin, Settings

class Database:
    def __init__(self, db_path: str = "contest_bot.db"):
        self.db_path = db_path
        self.connection = None
    
    async def init_db(self):
        self.connection = await aiosqlite.connect(self.db_path)
        await self.create_tables()
    
    async def close(self):
        if self.connection:
            await self.connection.close()
    
    async def create_tables(self):
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT DEFAULT 'en',
                is_active BOOLEAN DEFAULT 1,
                is_premium BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS contests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                image_url TEXT,
                button_text TEXT DEFAULT 'Join Contest',
                winners_count INTEGER DEFAULT 1,
                max_participants INTEGER,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT DEFAULT 'active',
                channel_id INTEGER,
                message_id INTEGER,
                view_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users (id)
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contest_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_winner BOOLEAN DEFAULT 0,
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
                announced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contest_id) REFERENCES contests (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self.connection.commit()
    
    async def create_user(self, user: User) -> User:
        cursor = await self.connection.execute("""
            INSERT INTO users (telegram_id, username, first_name, last_name, language_code)
            VALUES (?, ?, ?, ?, ?)
        """, (user.telegram_id, user.username, user.first_name, user.last_name, user.language_code))
        
        user.id = cursor.lastrowid
        await self.connection.commit()
        return user
    
    async def get_user(self, user_id: int) -> Optional[User]:
        cursor = await self.connection.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return User(*row)
        return None
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        cursor = await self.connection.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        if row:
            return User(*row)
        return None
    
    async def get_users_count(self) -> int:
        cursor = await self.connection.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0] if row else 0
    
    async def get_active_users(self) -> List[User]:
        cursor = await self.connection.execute("SELECT * FROM users WHERE is_active = 1")
        rows = await cursor.fetchall()
        return [User(*row) for row in rows]
    
    async def get_recent_users(self, limit: int) -> List[User]:
        cursor = await self.connection.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = await cursor.fetchall()
        return [User(*row) for row in rows]
    
    async def create_contest(self, contest: Contest) -> Contest:
        cursor = await self.connection.execute("""
            INSERT INTO contests (owner_id, title, description, image_url, button_text, winners_count, max_participants, start_time, end_time, status, channel_id, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (contest.owner_id, contest.title, contest.description, contest.image_url, contest.button_text, contest.winners_count, contest.max_participants, contest.start_time, contest.end_time, contest.status, contest.channel_id, contest.message_id))
        
        contest.id = cursor.lastrowid
        await self.connection.commit()
        return contest
    
    async def get_contest(self, contest_id: int) -> Optional[Contest]:
        cursor = await self.connection.execute("SELECT * FROM contests WHERE id = ?", (contest_id,))
        row = await cursor.fetchone()
        if row:
            return Contest(*row)
        return None
    
    async def get_contests_count(self) -> int:
        cursor = await self.connection.execute("SELECT COUNT(*) FROM contests")
        row = await cursor.fetchone()
        return row[0] if row else 0
    
    async def get_active_contests_count(self) -> int:
        cursor = await self.connection.execute("SELECT COUNT(*) FROM contests WHERE status = 'active'")
        row = await cursor.fetchone()
        return row[0] if row else 0
    
    async def get_active_contests(self, limit: int) -> List[Contest]:
        cursor = await self.connection.execute("SELECT * FROM contests WHERE status = 'active' ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = await cursor.fetchall()
        return [Contest(*row) for row in rows]
    
    async def get_recent_contests(self, limit: int) -> List[Contest]:
        cursor = await self.connection.execute("SELECT * FROM contests ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = await cursor.fetchall()
        return [Contest(*row) for row in rows]
    
    async def get_user_contests(self, user_id: int) -> List[Contest]:
        cursor = await self.connection.execute("SELECT * FROM contests WHERE owner_id = ? ORDER BY created_at DESC", (user_id,))
        rows = await cursor.fetchall()
        return [Contest(*row) for row in rows]
    
    async def update_contest_status(self, contest_id: int, status: str):
        await self.connection.execute("UPDATE contests SET status = ? WHERE id = ?", (status, contest_id))
        await self.connection.commit()
    
    async def create_participant(self, participant: Participant) -> Participant:
        cursor = await self.connection.execute("""
            INSERT INTO participants (contest_id, user_id)
            VALUES (?, ?)
        """, (participant.contest_id, participant.user_id))
        
        participant.id = cursor.lastrowid
        await self.connection.commit()
        return participant
    
    async def get_participant(self, contest_id: int, user_id: int) -> Optional[Participant]:
        cursor = await self.connection.execute("SELECT * FROM participants WHERE contest_id = ? AND user_id = ?", (contest_id, user_id))
        row = await cursor.fetchone()
        if row:
            return Participant(*row)
        return None
    
    async def get_participants_count(self, contest_id: int = None) -> int:
        if contest_id:
            cursor = await self.connection.execute("SELECT COUNT(*) FROM participants WHERE contest_id = ?", (contest_id,))
        else:
            cursor = await self.connection.execute("SELECT COUNT(*) FROM participants")
        row = await cursor.fetchone()
        return row[0] if row else 0
    
    async def get_contest_participants(self, contest_id: int) -> List[Participant]:
        cursor = await self.connection.execute("SELECT * FROM participants WHERE contest_id = ?", (contest_id,))
        rows = await cursor.fetchall()
        return [Participant(*row) for row in rows]
    
    async def get_user_participations(self, user_id: int) -> List[Participant]:
        cursor = await self.connection.execute("SELECT * FROM participants WHERE user_id = ? ORDER BY joined_at DESC", (user_id,))
        rows = await cursor.fetchall()
        return [Participant(*row) for row in rows]
    
    async def update_participant_winner_status(self, participant_id: int, is_winner: bool):
        await self.connection.execute("UPDATE participants SET is_winner = ? WHERE id = ?", (is_winner, participant_id))
        await self.connection.commit()
    
    async def create_winner(self, winner: Winner) -> Winner:
        cursor = await self.connection.execute("""
            INSERT INTO winners (contest_id, user_id, position)
            VALUES (?, ?, ?)
        """, (winner.contest_id, winner.user_id, winner.position))
        
        winner.id = cursor.lastrowid
        await self.connection.commit()
        return winner
    
    async def get_contest_winners(self, contest_id: int) -> List[Winner]:
        cursor = await self.connection.execute("SELECT * FROM winners WHERE contest_id = ? ORDER BY position", (contest_id,))
        rows = await cursor.fetchall()
        return [Winner(*row) for row in rows]
    
    async def create_admin(self, admin: Admin) -> Admin:
        cursor = await self.connection.execute("""
            INSERT INTO admins (username, password_hash)
            VALUES (?, ?)
        """, (admin.username, admin.password_hash))
        
        admin.id = cursor.lastrowid
        await self.connection.commit()
        return admin
    
    async def get_admin_by_username(self, username: str) -> Optional[Admin]:
        cursor = await self.connection.execute("SELECT * FROM admins WHERE username = ?", (username,))
        row = await cursor.fetchone()
        if row:
            return Admin(*row)
        return None

def get_db():
    return Database()
