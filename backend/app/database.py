"""MongoDB-подключение и индексы.

Единая коллекция `analyses` хранит все типы записей: звонки, чаты, лиды.
Старые коллекции `transcriptions` и `lead_analyses` удаляются на первом
старте после рефакторинга — данные пересчитываются.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

from .config import settings

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db]

users = db["users"]
analyses = db["analyses"]
system_meta = db["system_meta"]   # одноразовые маркеры миграций и тд
audio_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="call_audio")

# Legacy — оставляем ссылку, чтобы корректно дропнуть один раз
_legacy_transcriptions = db["transcriptions"]
_legacy_lead_analyses = db["lead_analyses"]


async def ensure_indexes() -> None:
    # Auth
    await users.create_index("login", unique=True)

    # ── analyses: единая коллекция для call/chat/lead ────────────────────────
    # 1. Список и dashboard — основная фильтрация
    await analyses.create_index([
        ("user_id", 1), ("kind", 1), ("status", 1), ("date", -1),
    ])
    # 2. Аналитика по операторам
    await analyses.create_index([
        ("user_id", 1), ("kind", 1), ("status", 1), ("manager_id", 1),
    ])
    # 3. Look-up по внешним ID
    await analyses.create_index(
        [("user_id", 1), ("kind", 1), ("call.bitrix_call_id", 1)],
        unique=True,
        partialFilterExpression={
            "kind": "call",
            "call.bitrix_call_id": {"$type": "string"},
        },
    )
    await analyses.create_index(
        [("user_id", 1), ("kind", 1), ("chat.bitrix_chat_id", 1)],
        unique=True,
        partialFilterExpression={
            "kind": "chat",
            "chat.bitrix_chat_id": {"$type": "string"},
        },
    )
    await analyses.create_index(
        [("user_id", 1), ("kind", 1), ("lead.bitrix_lead_id", 1)],
        unique=True,
        partialFilterExpression={
            "kind": "lead",
            "lead.bitrix_lead_id": {"$type": "string"},
        },
    )

    # ── Одноразовая чистка legacy + удаление мусорного маркера ───────────────
    # Маркер раньше клали в коллекцию users — теперь чистим, чтобы он не
    # попадал в выдачу пользователей.
    await users.delete_many({"login": {"$exists": False}})

    flag = await system_meta.find_one({"_id": "schema_v2"})
    if not flag:
        for coll in (_legacy_transcriptions, _legacy_lead_analyses):
            try:
                await coll.drop()
            except Exception:
                pass
        try:
            await audio_bucket.drop()
        except Exception:
            pass
        await system_meta.insert_one({"_id": "schema_v2", "version": 2})

    # Promote первого пользователя в админы, если админа ещё нет
    has_admin = await users.find_one({"is_admin": True})
    if not has_admin:
        first = await users.find_one({"login": {"$exists": True}}, sort=[("_id", 1)])
        if first:
            await users.update_one({"_id": first["_id"]}, {"$set": {"is_admin": True}})
