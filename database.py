import aiosqlite
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            await self.connection.execute("""
                INSERT INTO users (id, username, first_name, last_name, language_code)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, language_code))
        
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
                           end_time: str = None, max_participants: int = None) -> int:
        cursor = await self.connection.execute("""
            INSERT INTO contests 
            (owner_id, channel_id, title, description, image_file_id, 
             participate_button_text, winners_count, start_time, end_time, max_participants)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (owner_id, channel_id, title, description, image_file_id,
              participate_button_text, winners_count, start_time, end_time, max_participants))
        
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
    
    async def add_participant(self, contest_id: int, user_id: int) -> bool:
        try:
            await self.connection.execute("""
                INSERT INTO participants (contest_id, user_id) VALUES (?, ?)
            """, (contest_id, user_id))
            
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
    
    async def get_statistics(self) -> Dict[str, int]:
        stats = {}
        
        cursor = await self.connection.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = (await cursor.fetchone())[0]
        
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM users WHERE is_active = 1 AND is_banned = 0"
        )
        stats['active_users'] = (await cursor.fetchone())[0]
        
        cursor = await self.connection.execute("SELECT COUNT(*) FROM contests")
        stats['total_contests'] = (await cursor.fetchone())[0]
        
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM contests WHERE status = 'active'"
        )
        stats['active_contests'] = (await cursor.fetchone())[0]
        
        cursor = await self.connection.execute("SELECT COUNT(*) FROM participants")
        stats['total_participants'] = (await cursor.fetchone())[0]
        
        return stats

db = Database()
