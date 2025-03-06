from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    
    def get_db_name(self) -> str:
        """Extract database name from MongoDB URL"""
        return settings.MONGODB_URL.split('/')[-1].split('?')[0]

async def connect_to_mongo():
    """Create database connection."""
    logger.info("Connecting to MongoDB...")
    Database.client = AsyncIOMotorClient(settings.MONGODB_URL)
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
    if Database.client:
        Database.client.close()
        logger.info("MongoDB connection closed") 