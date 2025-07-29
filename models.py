from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, BigInteger, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    language_code = Column(String(10), default="en")
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    contests = relationship("Contest", back_populates="owner")
    participations = relationship("Participant", back_populates="user")

class Contest(Base):
    __tablename__ = "contests"
    
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    image_url = Column(String(500))
    button_text = Column(String(100), default="Join Contest")
    winners_count = Column(Integer, default=1)
    max_participants = Column(Integer)
    start_time = Column(DateTime, default=func.now())
    end_time = Column(DateTime)
    status = Column(String(20), default="active")
    channel_id = Column(BigInteger)
    message_id = Column(BigInteger)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    
    owner = relationship("User", back_populates="contests")
    participants = relationship("Participant", back_populates="contest")
    winners = relationship("Winner", back_populates="contest")

class Participant(Base):
    __tablename__ = "participants"
    
    id = Column(Integer, primary_key=True)
    contest_id = Column(Integer, ForeignKey("contests.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    joined_at = Column(DateTime, default=func.now())
    is_winner = Column(Boolean, default=False)
    
    contest = relationship("Contest", back_populates="participants")
    user = relationship("User", back_populates="participations")

class Winner(Base):
    __tablename__ = "winners"
    
    id = Column(Integer, primary_key=True)
    contest_id = Column(Integer, ForeignKey("contests.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    position = Column(Integer)
    announced_at = Column(DateTime, default=func.now())
    
    contest = relationship("Contest", back_populates="winners")
    user = relationship("User")

class Admin(Base):
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True)
    password_hash = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

class Settings(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
