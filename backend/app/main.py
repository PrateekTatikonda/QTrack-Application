from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import configure_logging

# Configure logging before importing routes so module-level service setup is logged.
configure_logging()

from app.api.routes import ai, health, queue  # noqa: E402
from app.db.session import Base, engine  # noqa: E402
import app.models  # noqa: E402,F401  (registers ORM models on Base.metadata)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router)
    application.include_router(queue.router)
    application.include_router(ai.router, prefix="/ai", tags=["AI Agent"])

    return application


app = create_app()
