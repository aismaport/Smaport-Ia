from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    plan = Column(String, default="free")  # free / pro
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Usage(Base):
    __tablename__ = "usage"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    endpoint = Column(String, nullable=False)
    cost = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
