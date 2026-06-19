from motor.motor_asyncio import AsyncIOMotorClient

from .config import settings

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db]

users = db["users"]
transcriptions = db["transcriptions"]


async def ensure_indexes() -> None:
    await users.create_index("login", unique=True)
    await transcriptions.create_index([("user_id", 1), ("created_at", -1)])
