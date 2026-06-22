from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, Form, HTTPException, Query, status

from ..auth import get_current_user
from ..config import settings
from ..database import audio_bucket, transcriptions
from ..models import (
    BitrixCall,
    BitrixCallsPage,
    BitrixChat,
    BitrixChatsPage,
    TranscriptionOut,
)
from ..openai_service import (
    SUPPORTED_TRANSCRIPTION_LANGUAGES,
    analyze_sales_call,
    normalize_language,
    transcribe_audio,
)
from .transcriptions import _doc_to_out

router = APIRouter(prefix="/api/bitrix", tags=["bitrix"])

MAX_RECORD_SIZE = 50 * 1024 * 1024  # 50 MB — записи звонков могут быть длиннее лимита OpenAI; обрежем при необходимости


def _webhook_base() -> str:
    base = (settings.bitrix_webhook_url or "").strip()
    if not base:
        raise HTTPException(
            status_code=503,
            detail="Bitrix24 webhook не настроен. Задайте BITRIX_WEBHOOK_URL в .env",
        )
    if not base.endswith("/"):
        base += "/"
    return base


async def _b24(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{_webhook_base()}{method}.json"
    print()
    print('url', url, payload)
    print()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Bitrix24 {method} вернул {resp.status_code}: {resp.text[:300]}",
            )
        data = resp.json()
    if "error" in data:
        raise HTTPException(
            status_code=502,
            detail=f"Bitrix24 {method}: {data.get('error_description') or data['error']}",
        )
    return data


def _normalize_call(raw: dict[str, Any], users_by_id: dict[str, str]) -> BitrixCall:
    raw_date = raw.get("CALL_START_DATE") or raw.get("DATE_CREATE")
    parsed_date: Optional[datetime] = None
    if raw_date:
        try:
            parsed_date = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
        except ValueError:
            parsed_date = None

    direction_map = {"1": "Входящий", "2": "Исходящий"}
    direction = direction_map.get(str(raw.get("CALL_TYPE", "")), "")

    portal_user_id = str(raw.get("PORTAL_USER_ID") or "")
    manager = users_by_id.get(portal_user_id, "")

    return BitrixCall(
        id=str(raw.get("ID") or raw.get("CALL_ID") or ""),
        phone=str(raw.get("PHONE_NUMBER") or ""),
        date=parsed_date,
        duration=int(raw.get("CALL_DURATION") or 0),
        direction=direction,
        manager=manager,
        manager_id=portal_user_id,
        record_url=str(raw.get("CALL_RECORD_URL") or raw.get("RECORD_FILE_ID") or ""),
    )


async def _fetch_users(ids: list[str]) -> dict[str, str]:
    ids = list({i for i in ids if i})
    if not ids:
        return {}
    data = await _b24("user.get", {"FILTER": {"ID": ids}})
    result: dict[str, str] = {}
    for u in data.get("result", []) or []:
        uid = str(u.get("ID"))
        name = " ".join(filter(None, [u.get("NAME"), u.get("LAST_NAME")])).strip() or u.get("EMAIL") or f"#{uid}"
        result[uid] = name
    return result


@router.get("/calls", response_model=BitrixCallsPage)
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    direction: Optional[str] = Query(None, description="in | out"),
    user=Depends(get_current_user),
) -> BitrixCallsPage:
    filt: dict[str, Any] = {}
    if date_from:
        filt[">=CALL_START_DATE"] = date_from
    if date_to:
        filt["<=CALL_START_DATE"] = date_to
    if direction == "in":
        filt["CALL_TYPE"] = 1
    elif direction == "out":
        filt["CALL_TYPE"] = 2

    start = (page - 1) * page_size
    data = await _b24(
        "voximplant.statistic.get",
        {
            "FILTER": filt,
            "SORT": "CALL_START_DATE",
            "ORDER": "DESC",
            "start": start,
        },
    )
    raw_items = data.get("result", []) or []
    total = int(data.get("total", len(raw_items)))

    user_ids = [str(r.get("PORTAL_USER_ID") or "") for r in raw_items]
    users_map = await _fetch_users(user_ids)

    items = [_normalize_call(r, users_map) for r in raw_items][:page_size]

    if items:
        cursor = transcriptions.find(
            {"user_id": user["_id"], "bitrix_call_id": {"$in": [c.id for c in items]}},
            {"_id": 1, "bitrix_call_id": 1, "status": 1},
        )
        analyzed = {doc["bitrix_call_id"]: doc async for doc in cursor}
        for c in items:
            doc = analyzed.get(c.id)
            if doc:
                c.transcription_id = str(doc["_id"])
                c.analyzed = doc.get("status") == "done"

    return BitrixCallsPage(items=items, total=total, page=page, page_size=page_size)


@router.post("/calls/{call_id}/analyze", response_model=TranscriptionOut)
async def analyze_call(
    call_id: str,
    language: Optional[str] = Form(None),
    user=Depends(get_current_user),
) -> TranscriptionOut:
    if language and language.strip().lower() not in SUPPORTED_TRANSCRIPTION_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")
    lang = normalize_language(language)

    existing = await transcriptions.find_one({"user_id": user["_id"], "bitrix_call_id": call_id})
    if existing and existing.get("status") == "done":
        return _doc_to_out(existing)

    data = await _b24("voximplant.statistic.get", {"FILTER": {"ID": call_id}})
    items = data.get("result") or []
    if not items:
        raise HTTPException(status_code=404, detail="Звонок не найден в Bitrix24")
    raw = items[0]

    users_map = await _fetch_users([str(raw.get("PORTAL_USER_ID") or "")])
    call = _normalize_call(raw, users_map)

    if not call.record_url:
        raise HTTPException(status_code=400, detail="У звонка нет записи (CALL_RECORD_URL пуст)")

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        resp = await client.get(call.record_url)
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Не удалось скачать запись звонка ({resp.status_code})",
            )
        audio_bytes = resp.content
    if not audio_bytes:
        raise HTTPException(status_code=502, detail="Пустая запись звонка")
    if len(audio_bytes) > MAX_RECORD_SIZE:
        raise HTTPException(status_code=413, detail="Запись звонка слишком большая (>50MB)")

    now = datetime.now(timezone.utc)
    filename = f"bitrix-call-{call_id}.mp3"
    base_doc = {
        "user_id": user["_id"],
        "filename": filename,
        "source": "bitrix_call",
        "bitrix_call_id": call_id,
        "bitrix_phone": call.phone,
        "bitrix_manager": call.manager,
        "bitrix_manager_id": call.manager_id,
        "bitrix_direction": call.direction,
        "bitrix_call_date": call.date,
        "duration": call.duration,
        "size": len(audio_bytes),
        "status": "processing",
        "language": lang,
        "created_at": now,
    }
    if existing:
        tid = existing["_id"]
        # Удаляем старую запись аудио, если была — заменим свежей.
        if existing.get("audio_file_id"):
            try:
                await audio_bucket.delete(existing["audio_file_id"])
            except Exception:
                pass
        await transcriptions.update_one({"_id": tid}, {"$set": base_doc})
    else:
        result = await transcriptions.insert_one(base_doc)
        tid = result.inserted_id

    audio_file_id = await audio_bucket.upload_from_stream(
        filename,
        audio_bytes,
        metadata={
            "user_id": user["_id"],
            "transcription_id": tid,
            "bitrix_call_id": call_id,
            "content_type": "audio/mpeg",
        },
    )
    await transcriptions.update_one(
        {"_id": tid},
        {"$set": {"audio_file_id": audio_file_id, "audio_content_type": "audio/mpeg"}},
    )

    try:
        text = await transcribe_audio(audio_bytes, filename, language=lang)
        sales = await analyze_sales_call(text, source="call")
        update = {
            "text": text,
            "sales_analysis": sales.model_dump(),
            "status": "done",
            "error": None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        await transcriptions.update_one(
            {"_id": tid}, {"$set": {"status": "failed", "error": str(exc)[:500]}}
        )
        raise HTTPException(status_code=502, detail=f"Анализ не выполнен: {exc}")

    await transcriptions.update_one({"_id": tid}, {"$set": update})
    fresh = await transcriptions.find_one({"_id": tid})
    return _doc_to_out(fresh)


# ============================================================================
# Open Lines (чаты)
# ============================================================================

CHAT_PROVIDER_TYPES = ("IMOPENLINES_SESSION",)


def _parse_b24_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_chat(raw: dict[str, Any], users_by_id: dict[str, str]) -> BitrixChat:
    params = raw.get("PROVIDER_PARAMS") or {}
    if isinstance(params, str):
        params = {}
    session_id = str(raw.get("ASSOCIATED_ENTITY_ID") or raw.get("ID") or "")
    operator_id = str(raw.get("RESPONSIBLE_ID") or "")
    channel = str(
        params.get("LINE_NAME")
        or params.get("CONNECTOR")
        or raw.get("PROVIDER_GROUP_ID")
        or ""
    )
    client = str(params.get("USER_NAME") or params.get("FROM") or "")
    return BitrixChat(
        id=session_id,
        subject=str(raw.get("SUBJECT") or "").strip(),
        channel=channel,
        client=client,
        operator=users_by_id.get(operator_id, ""),
        operator_id=operator_id,
        started_at=_parse_b24_date(raw.get("CREATED") or raw.get("DATE_CREATE")),
    )


@router.get("/chats", response_model=BitrixChatsPage)
async def list_chats(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user=Depends(get_current_user),
) -> BitrixChatsPage:
    flt: dict[str, Any] = {
        # "TYPE_ID": 4,
        # "PROVIDER_TYPE_ID": list(CHAT_PROVIDER_TYPES),
    }
    if date_from:
        flt[">=CREATED"] = date_from
    if date_to:
        flt["<=CREATED"] = date_to

    start = (page - 1) * page_size
    data = await _b24(
        "crm.activity.list",
        {
            "filter": flt,
            "order": {"CREATED": "DESC"},
            # "select": [
            #     "ID",
            #     "SUBJECT",
            #     "RESPONSIBLE_ID",
            #     "CREATED",
            #     "ASSOCIATED_ENTITY_ID",
            #     "PROVIDER_PARAMS",
            #     "PROVIDER_GROUP_ID",
            #     "PROVIDER_TYPE_ID",
            #     "DESCRIPTION",
            # ],
            "start": start,
        },
    )
    raw_items = data.get("result", []) or []
    total = int(data.get("total", len(raw_items)))

    user_ids = [str(r.get("RESPONSIBLE_ID") or "") for r in raw_items]
    users_map = await _fetch_users(user_ids)

    items = [_normalize_chat(r, users_map) for r in raw_items][:page_size]

    if items:
        cursor = transcriptions.find(
            {"user_id": user["_id"], "bitrix_chat_id": {"$in": [c.id for c in items]}},
            {"_id": 1, "bitrix_chat_id": 1, "status": 1},
        )
        analyzed = {doc["bitrix_chat_id"]: doc async for doc in cursor}
        for c in items:
            doc = analyzed.get(c.id)
            if doc:
                c.transcription_id = str(doc["_id"])
                c.analyzed = doc.get("status") == "done"

    return BitrixChatsPage(items=items, total=total, page=page, page_size=page_size)


async def _fetch_chat_history(session_id: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Возвращает (messages, author_names). Падает с понятным сообщением, если webhook не отдаёт историю."""
    try:
        data = await _b24("imopenlines.session.history.get", {"SESSION_ID": session_id, "LIMIT": 500})
    except HTTPException as exc:
        # имя метода может отличаться у разных вебхуков — пробуем alt-метод
        if exc.status_code == 502 and "imopenlines.session.history" in (exc.detail or ""):
            data = await _b24("imopenlines.session.history", {"SESSION_ID": session_id, "LIMIT": 500})
        else:
            raise

    result = data.get("result") or {}
    if isinstance(result, dict):
        messages = result.get("messages") or result.get("MESSAGES") or []
        users_raw = result.get("users") or result.get("USERS") or []
    else:
        messages = result if isinstance(result, list) else []
        users_raw = []

    authors: dict[str, str] = {}
    for u in users_raw:
        if not isinstance(u, dict):
            continue
        uid = str(u.get("id") or u.get("ID") or "")
        if uid:
            authors[uid] = (
                u.get("name")
                or u.get("NAME")
                or " ".join(filter(None, [u.get("first_name"), u.get("last_name")])).strip()
                or f"#{uid}"
            )

    return list(messages), authors


def _format_chat(messages: list[dict[str, Any]], authors: dict[str, str], operator_id: str) -> str:
    lines: list[str] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        author_id = str(m.get("author_id") or m.get("AUTHOR_ID") or "")
        text = m.get("text") or m.get("TEXT") or m.get("MESSAGE") or ""
        if not text:
            continue
        if author_id and author_id == operator_id:
            role = "Менеджер"
        elif author_id and author_id in authors:
            role = authors[author_id]
        else:
            role = "Клиент"
        lines.append(f"{role}: {text}".strip())
    return "\n".join(lines)


@router.post("/chats/{session_id}/analyze", response_model=TranscriptionOut)
async def analyze_chat(session_id: str, user=Depends(get_current_user)) -> TranscriptionOut:
    existing = await transcriptions.find_one({"user_id": user["_id"], "bitrix_chat_id": session_id})
    if existing and existing.get("status") == "done":
        return _doc_to_out(existing)

    # Подтянем краткую инфу о сессии через crm.activity для имени канала/оператора
    activity_data = await _b24(
        "crm.activity.list",
        {
            "filter": {
                "TYPE_ID": 4,
                "PROVIDER_TYPE_ID": list(CHAT_PROVIDER_TYPES),
                "ASSOCIATED_ENTITY_ID": session_id,
            },
            "select": [
                "ID",
                "SUBJECT",
                "RESPONSIBLE_ID",
                "CREATED",
                "ASSOCIATED_ENTITY_ID",
                "PROVIDER_PARAMS",
            ],
        },
    )
    act_items = activity_data.get("result") or []
    raw = act_items[0] if act_items else {}
    users_map = await _fetch_users([str(raw.get("RESPONSIBLE_ID") or "")])
    chat = _normalize_chat(raw, users_map) if raw else BitrixChat(id=session_id)

    messages, authors = await _fetch_chat_history(session_id)
    if not messages:
        raise HTTPException(status_code=400, detail="История чата пуста или недоступна")

    text = _format_chat(messages, authors, chat.operator_id)
    if not text.strip():
        raise HTTPException(status_code=400, detail="В сообщениях нет текста")

    now = datetime.now(timezone.utc)
    base_doc = {
        "user_id": user["_id"],
        "filename": f"bitrix-chat-{session_id}.txt",
        "source": "bitrix_chat",
        "bitrix_chat_id": session_id,
        "bitrix_channel": chat.channel,
        "bitrix_client": chat.client,
        "bitrix_manager": chat.operator,
        "bitrix_manager_id": chat.operator_id,
        "bitrix_subject": chat.subject,
        "bitrix_call_date": chat.started_at,
        "messages_count": len(messages),
        "status": "processing",
        "created_at": now,
        "text": text,
    }
    if existing:
        tid = existing["_id"]
        await transcriptions.update_one({"_id": tid}, {"$set": base_doc})
    else:
        result = await transcriptions.insert_one(base_doc)
        tid = result.inserted_id

    try:
        sales = await analyze_sales_call(text, source="chat")
        update = {
            "sales_analysis": sales.model_dump(),
            "status": "done",
            "error": None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        await transcriptions.update_one(
            {"_id": tid}, {"$set": {"status": "failed", "error": str(exc)[:500]}}
        )
        raise HTTPException(status_code=502, detail=f"Анализ не выполнен: {exc}")

    await transcriptions.update_one({"_id": tid}, {"$set": update})
    fresh = await transcriptions.find_one({"_id": tid})
    return _doc_to_out(fresh)
