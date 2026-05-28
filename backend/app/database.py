"""
Database configuration using Motor (async MongoDB driver)
Handles connection pooling and database initialization
"""

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT
from app.config import settings
import logging

logger = logging.getLogger(__name__)

client: AsyncIOMotorClient = None
db = None


async def init_db():
    """Initialize MongoDB connection and create indexes"""
    global client, db
    
    client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        maxPoolSize=settings.DB_MAX_POOL_SIZE,
        minPoolSize=settings.DB_MIN_POOL_SIZE,
        serverSelectionTimeoutMS=5000
    )
    
    db = client[settings.DB_NAME]
    
    # Verify connection
    await client.admin.command('ping')
    logger.info(f"Connected to MongoDB: {settings.DB_NAME}")
    
    # Create indexes for performance
    await create_indexes()


async def create_indexes():
    """Create database indexes for optimized queries"""
    
    # Users collection indexes
    await db.users.create_indexes([
        IndexModel([("email", ASCENDING)], unique=True),
        IndexModel([("username", ASCENDING)], unique=True),
        IndexModel([("role", ASCENDING)]),
        IndexModel([("created_at", DESCENDING)]),
    ])
    
    # Projects collection indexes
    await db.projects.create_indexes([
        IndexModel([("name", TEXT), ("description", TEXT)]),
        IndexModel([("owner_id", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("team_members", ASCENDING)]),
        IndexModel([("created_at", DESCENDING)]),
    ])
    
    # Tasks collection indexes
    await db.tasks.create_indexes([
        IndexModel([("project_id", ASCENDING)]),
        IndexModel([("assignee_id", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("priority", ASCENDING)]),
        IndexModel([("due_date", ASCENDING)]),
        IndexModel([("title", TEXT), ("description", TEXT)]),
        IndexModel([("project_id", ASCENDING), ("status", ASCENDING)]),
    ])
    
    # Activity logs collection
    await db.activity_logs.create_indexes([
        IndexModel([("user_id", ASCENDING)]),
        IndexModel([("project_id", ASCENDING)]),
        IndexModel([("timestamp", DESCENDING)]),
        IndexModel([("action", ASCENDING)]),
    ])
    
    logger.info("Database indexes created successfully")


async def close_db():
    """Close database connection"""
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")


def get_db():
    """Dependency to get database instance"""
    return db


def get_collection(collection_name: str):
    """Get a specific collection"""
    return db[collection_name]
