from pymongo import ASCENDING, AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.config import settings
from app.utils.log_utils import LogUtils

logger = LogUtils.get_logger(__name__)


class MongoDBService:
    """Own the shared MongoDB client: connect, indexes, collections and shutdown.

    Sync variant (Flask, or sync code wrapped in asyncio.to_thread): use `MongoClient` from
    `pymongo`, `Collection`/`Database` types, and drop every `async`/`await`.
    """

    client: AsyncMongoClient | None = None
    database: AsyncDatabase | None = None
    indexes_ready: bool = False

    @classmethod
    async def connect(cls) -> None:
        """Create the client once at startup; the app still starts if MongoDB is down."""
        if not settings.mongodb_uri:
            logger.error("MongoDB is not configured | setting=MONGODB_URI")
            return
        cls.client = AsyncMongoClient(
            settings.mongodb_uri,
            maxPoolSize=settings.mongodb_max_pool_size,
            minPoolSize=settings.mongodb_min_pool_size,
            maxIdleTimeMS=60000,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=20000,
            waitQueueTimeoutMS=5000,
            retryWrites=True,
            tz_aware=True,
        )
        cls.database = cls.client[settings.mongodb_database]
        try:
            await cls.client.admin.command("ping")
            await cls.create_indexes()
            logger.info("MongoDB connected | database=%s", settings.mongodb_database)
        except PyMongoError as exc:
            logger.error("MongoDB unavailable at startup | error_type=%s", type(exc).__name__)

    @classmethod
    async def close(cls) -> None:
        """Close the client and its pooled connections at shutdown."""
        if cls.client is not None:
            await cls.client.close()
            logger.info("MongoDB connection closed")

    @classmethod
    async def get_database(cls) -> AsyncDatabase:
        """Return the shared database; creates missing indexes once MongoDB is reachable."""
        if cls.database is None:
            raise ConnectionError("Database is not configured.")
        if not cls.indexes_ready:
            await cls.create_indexes()
        return cls.database

    @classmethod
    async def get_collection(cls, name: str) -> AsyncCollection:
        """Return a collection from the shared database."""
        database = await cls.get_database()
        return database[name]

    @classmethod
    async def check_connection(cls) -> None:
        """Ping MongoDB for /health; raises when it is unreachable."""
        database = await cls.get_database()
        await database.client.admin.command("ping")

    @classmethod
    async def create_indexes(cls) -> None:
        """Create named indexes; safe to run again because create_index is idempotent."""
        database = cls.database
        await database.users.create_index([("email", ASCENDING)], unique=True, name="users_email_unique")
        # Add one line per index the project's queries need (import DESCENDING when used), for example:
        # await database.chats.create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)], name="chats_user_updated_idx")
        # await database.oauth_states.create_index("expires_at", expireAfterSeconds=0, name="oauth_states_expires_ttl")
        cls.indexes_ready = True
        logger.info("MongoDB indexes ready")

