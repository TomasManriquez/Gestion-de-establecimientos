from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.database.database_service import db_service
from app.auth.auth_controller import router as auth_router
from app.establishments.establishments_controller import router as est_router
from app.counterparts.counterparts_controller import router as cp_router
from app.metrics.metrics_controller import router as metrics_router
from app.analytics.analytics_controller import router as analytics_router

logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to MongoDB on startup
    logger.info("Initializing database connection...")
    await db_service.connect()
    yield
    # Close database connection on shutdown
    logger.info("Closing database connection...")
    await db_service.close()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API para la gestión centralizada de establecimientos de educación pública",
    version="1.0.0",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(est_router)
app.include_router(cp_router)
app.include_router(metrics_router)
app.include_router(analytics_router)

@app.get("/")
async def root():
    return {
        "app": settings.PROJECT_NAME,
        "status": "online",
        "message": "API centralizada activa. Consulte la documentación en /docs"
    }
