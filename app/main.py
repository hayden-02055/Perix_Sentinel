from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.logger import get_logger
from app.interface.api.health import router as health_router
from app.interface.api.collect import router as collect_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Perix Sentinel starting up [env=%s]", settings.app_env)
    yield
    logger.info("Perix Sentinel shutting down")


app = FastAPI(
    title="Perix Sentinel",
    description="AI/Tech trend intelligence system",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(collect_router)
