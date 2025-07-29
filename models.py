from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class User:
    id: Optional[int] = None
    telegram_id: int = 0
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: str = "en"
    is_active: bool = True
    is_premium: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class Contest:
    id: Optional[int] = None
    owner_id: int = 0
    title: str = ""
    description: Optional[str] = None
    image_url: Optional[str] = None
    button_text: str = "Join Contest"
    winners_count: int = 1
    max_participants: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str = "active"
    channel_id: Optional[int] = None
    message_id: Optional[int] = None
    view_count: int = 0
    created_at: Optional[datetime] = None

@dataclass
class Participant:
    id: Optional[int] = None
    contest_id: int = 0
    user_id: int = 0
    joined_at: Optional[datetime] = None
    is_winner: bool = False

@dataclass
class Winner:
    id: Optional[int] = None
    contest_id: int = 0
    user_id: int = 0
    position: int = 1
    announced_at: Optional[datetime] = None

@dataclass
class Admin:
    id: Optional[int] = None
    username: str = ""
    password_hash: str = ""
    is_active: bool = True
    created_at: Optional[datetime] = None

@dataclass
class Settings:
    id: Optional[int] = None
    key: str = ""
    value: str = ""
    updated_at: Optional[datetime] = None
