import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db, get_redis
from app.db.session import Base
from app.main import app


@pytest.fixture
def fake_redis():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autocommit=False, autoflush=False)
    engine.dispose()


@pytest.fixture
def client(fake_redis, session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: fake_redis
    # Not used as a context manager, so the lifespan (Postgres create_all) is skipped.
    yield TestClient(app)
    app.dependency_overrides.clear()
