from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from app.services.db import Base

class QueueLog(Base):
    __tablename__ = "queue_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String)
    branch_id = Column(String)
    status = Column(String)
    joined_at = Column(DateTime, server_default=func.now())
    called_at = Column(DateTime, nullable=True)
    skipped = Column(Boolean, default=False)