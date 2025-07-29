from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base, Admin
from config import settings
from utils import hash_password

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def init_db():
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        if not db.query(Admin).first():
            admin = Admin(
                username="admin",
                password_hash=hash_password("admin123")
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()
