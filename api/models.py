from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime


class Scan(Base):
    __tablename__ = "scans"
    id = Column(Integer, primary_key=True, index=True)
    post_url = Column(String, nullable=False)
    mode = Column(String, default="ml")
    threshold = Column(Float, default=0.7)
    scrolls = Column(Integer, default=50)
    scroll_delay = Column(Integer, default=1500)
    status = Column(String, default="enqueued")
    result_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    comments = relationship("Comment", back_populates="scan")


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"))
    original = Column(String)
    normalized = Column(String)
    username = Column(String)
    link = Column(String)
    matched_words = Column(JSON, default=list)
    category = Column(String)
    confidence = Column(Float)
    scan = relationship("Scan", back_populates="comments")
