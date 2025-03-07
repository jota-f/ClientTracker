from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    database = None
    
    def get_db_name(self) -> str:
        """Extract database name from MongoDB URL"""
        return settings.MONGODB_URL.split('/')[-1].split('?')[0]

    @classmethod
    async def connect(cls):
        cls.client = AsyncIOMotorClient(settings.MONGODB_URL)
        cls.database = cls.client["clienttracker"]

    @classmethod
    async def close(cls):
        cls.client.close()

async def connect_to_mongo():
    """Create database connection."""
    logger.info("Connecting to MongoDB...")
    await Database.connect()
    try:
        # Verify the connection
        await Database.client.admin.command('ping')
        db_name = Database().get_db_name()
        logger.info(f"Connected to MongoDB. Database: {db_name}")
    except ConnectionFailure:
        logger.error("Server not available")
        raise

async def close_mongo_connection():
    """Close database connection."""
    logger.info("Closing MongoDB connection...")
    await Database.close()
    logger.info("MongoDB connection closed")

async def get_db():
    """Get the database instance."""
    return Database.database 