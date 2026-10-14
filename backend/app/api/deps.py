from typing import Iterator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.redis_client import get_redis

__all__ = ["get_db", "get_redis"]


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
