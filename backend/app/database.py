from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

from .config import settings

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db]

users = db["users"]
transcriptions = db["transcriptions"]
audio_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="call_audio")


async def ensure_indexes() -> None:
    await users.create_index("login", unique=True)
    await transcriptions.create_index([("user_id", 1), ("created_at", -1)])
    await transcriptions.create_index([("user_id", 1), ("bitrix_call_date", -1)])
    await transcriptions.create_index([("user_id", 1), ("bitrix_manager_id", 1)])
    await transcriptions.create_index(
        [("user_id", 1), ("bitrix_call_id", 1)],
        unique=True,
        partialFilterExpression={"bitrix_call_id": {"$type": "string"}},
    )
    await transcriptions.create_index(
        [("user_id", 1), ("bitrix_chat_id", 1)],
        unique=True,
        partialFilterExpression={"bitrix_chat_id": {"$type": "string"}},
    )

    # Если в системе нет ни одного админа — повышаем самого старого пользователя.
    has_admin = await users.find_one({"is_admin": True})
    if not has_admin:
        first = await users.find_one({}, sort=[("_id", 1)])
        if first:
            await users.update_one({"_id": first["_id"]}, {"$set": {"is_admin": True}})
