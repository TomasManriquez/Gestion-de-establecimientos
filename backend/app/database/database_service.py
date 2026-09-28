import logging
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.database import seed_service

# Setup logging
logger = logging.getLogger("database")
logging.basicConfig(level=logging.INFO)

class DatabaseService:
    def __init__(self):
        self.client = None
        self.db = None
    #initialize the database connection
    async def connect(self):
        try:
            self.client = AsyncIOMotorClient(settings.MONGODB_URL)
            self.db = self.client[settings.DATABASE_NAME]
            logger.info(f"Connected to MongoDB at {settings.MONGODB_URL}")
            # Run auto-seed
            await self.seed_if_empty()
            await self.ensure_indexes()
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise e

    async def close(self):
        if self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")

    async def seed_if_empty(self):
        """Delega en app.database.seed_service — ver ese módulo para el detalle
        de la descomposición de establishments.json en las tres colecciones."""
        await seed_service.seed_if_empty(self.db)

    async def ensure_indexes(self):
        """BE-01: Crea índices optimizados en todas las colecciones.
        Idempotente: usar create_index() con motor/pymongo es seguro si el índice ya existe."""
        logger.info("Ensuring MongoDB indexes...")

        # Establishments
        await self.db.establishments.create_index("rbd", unique=True, background=True)
        await self.db.establishments.create_index([("comuna", 1), ("area_type", 1)], background=True)
        await self.db.establishments.create_index("name", background=True)
        await self.db.establishments.create_index("general_info.category", background=True)

        # Counterparts
        await self.db.counterparts.create_index("rbd", background=True)
        await self.db.counterparts.create_index([("rbd", 1), ("role", 1)], background=True)

        # Metrics
        await self.db.metrics.create_index([("rbd", 1), ("year", -1)], unique=True, background=True)
        await self.db.metrics.create_index("year", background=True)

        logger.info("MongoDB indexes ensured.")

db_service = DatabaseService()
