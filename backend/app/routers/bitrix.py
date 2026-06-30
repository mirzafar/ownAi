"""Интеграция с Bitrix24: звонки, чаты, лиды.

После рефакторинга все запуски анализа пишут в единую коллекцию `analyses`
через `analysis_service`. Этот файл содержит только Bitrix-специфичный код
(нормализация ответов API, парсинг карточек лидов) + тонкие endpoint-ы.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)

from ..auth import get_current_user
from ..config import settings
from ..database import analyses, audio_bucket
from ..models import (
    AnalysisOut,
    BitrixCall,
    BitrixCallsPage,
    BitrixChat,
    BitrixChatsPage,
    BitrixContactValue,
    BitrixLead,
    BitrixLeadActivity,
    BitrixLeadDetail,
    BitrixLeadStatus,
    BitrixLeadTimelineEntry,
    BitrixLeadsPage,
    LeadCallRef,
)
from ..openai_service import analyze_lead_aggregate, analyze_unit, transcribe_audio
from ..services import analysis_service as svc

router = APIRouter(prefix="/api/bitrix", tags=["bitrix"])

MAX_RECORD_SIZE = 50 * 1024 * 1024


# ═══════════════════════════════════════════════════════════════════════════
# Низкоуровневые helper-ы для Bitrix REST
# ═══════════════════════════════════════════════════════════════════════════

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


def _portal_base() -> str:
    base = (settings.bitrix_webhook_url or "").strip()
    if not base:
        return ""
    idx = base.find("/rest/")
    if idx == -1:
        return base.rstrip("/") + "/"
    return base[: idx + 1]


def _lead_portal_url(lead_id: str) -> str:
    portal = _portal_base()
    if not portal or not lead_id:
        return ""
    return f"{portal}crm/lead/details/{lead_id}/"


async def _b24(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{_webhook_base()}{method}.json"
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


def _parse_b24_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_b24_iso(value: Optional[str], end_of_day: bool = False) -> Optional[str]:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if "T" in raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
        except ValueError:
            return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt.isoformat()


async def _fetch_users(ids: list[str]) -> dict[str, str]:
    ids = list({i for i in ids if i})
    if not ids:
        return {}
    data = await _b24("user.get", {"FILTER": {"ID": ids}})
    out: dict[str, str] = {}
    for u in data.get("result", []) or []:
        uid = str(u.get("ID"))
        name = " ".join(filter(None, [u.get("NAME"), u.get("LAST_NAME")])).strip() or u.get("EMAIL") or f"#{uid}"
        out[uid] = name
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Звонки
# ═══════════════════════════════════════════════════════════════════════════

def _normalize_call(raw: dict[str, Any], users_by_id: dict[str, str]) -> BitrixCall:
    direction_map = {"1": "Входящий", "2": "Исходящий"}
    portal_user_id = str(raw.get("PORTAL_USER_ID") or "")
    return BitrixCall(
        id=str(raw.get("ID") or raw.get("CALL_ID") or ""),
        phone=str(raw.get("PHONE_NUMBER") or ""),
        date=_parse_b24_dt(raw.get("CALL_START_DATE") or raw.get("DATE_CREATE")),
        duration=int(raw.get("CALL_DURATION") or 0),
        direction=direction_map.get(str(raw.get("CALL_TYPE", "")), ""),
        manager=users_by_id.get(portal_user_id, ""),
        manager_id=portal_user_id,
        record_url=str(raw.get("CALL_RECORD_URL") or raw.get("RECORD_FILE_ID") or ""),
    )


async def _enrich_calls_with_analysis(user: dict[str, Any], calls: list[BitrixCall]) -> None:
    if not calls:
        return
    ids = [c.id for c in calls if c.id]
    if not ids:
        return
    cursor = analyses.find(
        {"user_id": user["_id"], "kind": "call", "call.bitrix_call_id": {"$in": ids}},
        {"_id": 1, "call.bitrix_call_id": 1, "status": 1},
    )
    by_call: dict[str, dict] = {}
    async for d in cursor:
        cid = (d.get("call") or {}).get("bitrix_call_id") or ""
        by_call[str(cid)] = d
    for c in calls:
        d = by_call.get(c.id)
        if d:
            c.analysis_id = str(d["_id"])
            c.analyzed = d.get("status") == "done"


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
        {"FILTER": filt, "SORT": "CALL_START_DATE", "ORDER": "DESC", "start": start},
    )
    raw_items = data.get("result", []) or []
    total = int(data.get("total", len(raw_items)))

    users_map = await _fetch_users([str(r.get("PORTAL_USER_ID") or "") for r in raw_items])
    items = [_normalize_call(r, users_map) for r in raw_items][:page_size]
    await _enrich_calls_with_analysis(user, items)
    return BitrixCallsPage(items=items, total=total, page=page, page_size=page_size)


async def _ensure_call_analyzed(
    user: dict[str, Any],
    raw: dict[str, Any],
    users_map: dict[str, str],
) -> tuple[Optional[dict], str]:
    """Возвращает (документ analyses, reason). reason="" — успех.

    Если документ уже done — возвращается как есть. Иначе скачиваем запись,
    транскрибируем и оцениваем.
    """
    call = _normalize_call(raw, users_map)
    if not call.id:
        return None, "invalid_id"

    existing = await analyses.find_one({
        "user_id": user["_id"], "kind": "call", "call.bitrix_call_id": call.id,
    })
    if existing and existing.get("status") == "done":
        return existing, ""

    if not call.record_url:
        return None, "no_record"

    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            resp = await client.get(call.record_url)
            if resp.status_code >= 400:
                return None, f"download_failed:{resp.status_code}"
            audio_bytes = resp.content
        if not audio_bytes:
            return None, "empty_recording"
        if len(audio_bytes) > MAX_RECORD_SIZE:
            return None, "too_large"

        # Заливаем аудио в GridFS
        filename = f"bitrix-call-{call.id}.mp3"
        # Удалим старый аудио-файл если был
        if existing and existing.get("audio_file_id"):
            try:
                await audio_bucket.delete(existing["audio_file_id"])
            except Exception:
                pass
        audio_file_id = await audio_bucket.upload_from_stream(
            filename, audio_bytes,
            metadata={
                "user_id": user["_id"], "bitrix_call_id": call.id,
                "content_type": "audio/mpeg",
            },
        )

        text = await transcribe_audio(audio_bytes, filename)
        scoring = await analyze_unit(text, source="call")

        doc = await svc.upsert_call(
            user_id=user["_id"],
            bitrix_call_id=call.id,
            title=filename,
            date=call.date,
            duration=call.duration,
            phone=call.phone,
            direction=call.direction,
            manager=call.manager,
            manager_id=call.manager_id,
            record_url=call.record_url,
            text=text,
            scoring=scoring,
            audio_file_id=audio_file_id,
            audio_content_type="audio/mpeg",
        )
        return doc, ""
    except Exception as exc:
        return None, f"failed:{str(exc)[:200]}"


def _skip_reason_to_http(reason: str) -> HTTPException:
    if reason == "no_record":
        return HTTPException(status_code=400, detail="У звонка нет записи")
    if reason == "empty_recording":
        return HTTPException(status_code=502, detail="Пустая запись звонка")
    if reason == "too_large":
        return HTTPException(status_code=413, detail="Запись слишком большая (>50MB)")
    if reason.startswith("download_failed:"):
        return HTTPException(status_code=502, detail=f"Не удалось скачать запись ({reason.split(':', 1)[1]})")
    if reason.startswith("failed:"):
        return HTTPException(status_code=502, detail=f"Анализ не выполнен: {reason.split(':', 1)[1]}")
    return HTTPException(status_code=502, detail=f"Анализ не выполнен: {reason}")


@router.post("/calls/{call_id}/analyze", response_model=AnalysisOut)
async def analyze_call(call_id: str, user=Depends(get_current_user)) -> AnalysisOut:
    existing = await analyses.find_one({
        "user_id": user["_id"], "kind": "call", "call.bitrix_call_id": call_id,
    })
    if existing and existing.get("status") == "done":
        return svc.doc_to_out(existing)

    data = await _b24("voximplant.statistic.get", {"FILTER": {"ID": call_id}})
    items = data.get("result") or []
    if not items:
        raise HTTPException(status_code=404, detail="Звонок не найден в Bitrix24")
    raw = items[0]
    users_map = await _fetch_users([str(raw.get("PORTAL_USER_ID") or "")])

    doc, reason = await _ensure_call_analyzed(user, raw, users_map)
    if doc:
        return svc.doc_to_out(doc)
    raise _skip_reason_to_http(reason)


# ═══════════════════════════════════════════════════════════════════════════
# Чаты
# ═══════════════════════════════════════════════════════════════════════════

CHAT_PROVIDER_TYPES = ("IMOPENLINES_SESSION",)


def _normalize_chat(raw: dict[str, Any], users_by_id: dict[str, str]) -> BitrixChat:
    params = raw.get("PROVIDER_PARAMS") or {}
    if isinstance(params, str):
        params = {}
    session_id = str(raw.get("ASSOCIATED_ENTITY_ID") or raw.get("ID") or "")
    operator_id = str(raw.get("RESPONSIBLE_ID") or "")
    channel = str(
        params.get("LINE_NAME") or params.get("CONNECTOR")
        or raw.get("PROVIDER_GROUP_ID") or ""
    )
    client = str(params.get("USER_NAME") or params.get("FROM") or "")
    return BitrixChat(
        id=session_id,
        subject=str(raw.get("SUBJECT") or "").strip(),
        channel=channel,
        client=client,
        operator=users_by_id.get(operator_id, ""),
        operator_id=operator_id,
        started_at=_parse_b24_dt(raw.get("CREATED") or raw.get("DATE_CREATE")),
    )


@router.get("/chats", response_model=BitrixChatsPage)
async def list_chats(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user=Depends(get_current_user),
) -> BitrixChatsPage:
    flt: dict[str, Any] = {}
    if date_from:
        flt[">=CREATED"] = date_from
    if date_to:
        flt["<=CREATED"] = date_to

    start = (page - 1) * page_size
    data = await _b24(
        "crm.activity.list",
        {"filter": flt, "order": {"CREATED": "DESC"}, "start": start},
    )
    raw_items = data.get("result", []) or []
    total = int(data.get("total", len(raw_items)))

    users_map = await _fetch_users([str(r.get("RESPONSIBLE_ID") or "") for r in raw_items])
    items = [_normalize_chat(r, users_map) for r in raw_items][:page_size]

    if items:
        ids = [c.id for c in items if c.id]
        cursor = analyses.find(
            {"user_id": user["_id"], "kind": "chat", "chat.bitrix_chat_id": {"$in": ids}},
            {"_id": 1, "chat.bitrix_chat_id": 1, "status": 1},
        )
        by_id: dict[str, dict] = {}
        async for d in cursor:
            by_id[str((d.get("chat") or {}).get("bitrix_chat_id") or "")] = d
        for c in items:
            d = by_id.get(c.id)
            if d:
                c.analysis_id = str(d["_id"])
                c.analyzed = d.get("status") == "done"

    return BitrixChatsPage(items=items, total=total, page=page, page_size=page_size)


async def _fetch_chat_history(session_id: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    try:
        data = await _b24("imopenlines.session.history.get", {"SESSION_ID": session_id, "LIMIT": 500})
    except HTTPException as exc:
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
                u.get("name") or u.get("NAME")
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


@router.post("/chats/{session_id}/analyze", response_model=AnalysisOut)
async def analyze_chat(session_id: str, user=Depends(get_current_user)) -> AnalysisOut:
    existing = await analyses.find_one({
        "user_id": user["_id"], "kind": "chat", "chat.bitrix_chat_id": session_id,
    })
    if existing and existing.get("status") == "done":
        return svc.doc_to_out(existing)

    activity_data = await _b24(
        "crm.activity.list",
        {
            "filter": {
                "TYPE_ID": 4,
                "PROVIDER_TYPE_ID": list(CHAT_PROVIDER_TYPES),
                "ASSOCIATED_ENTITY_ID": session_id,
            },
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

    try:
        scoring = await analyze_unit(text, source="chat")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Анализ не выполнен: {exc}")

    doc = await svc.upsert_chat(
        user_id=user["_id"],
        bitrix_chat_id=session_id,
        title=f"chat-{session_id}",
        date=chat.started_at,
        channel=chat.channel,
        client=chat.client,
        subject=chat.subject,
        manager=chat.operator,
        manager_id=chat.operator_id,
        messages_count=len(messages),
        text=text,
        scoring=scoring,
    )
    return svc.doc_to_out(doc)


# ═══════════════════════════════════════════════════════════════════════════
# Лиды — справочники
# ═══════════════════════════════════════════════════════════════════════════

LEAD_PAGE_SIZE_MAX = 20


async def _fetch_status_list(entity_id: str) -> list[BitrixLeadStatus]:
    data = await _b24("crm.status.list", {"filter": {"ENTITY_ID": entity_id}})
    rows = data.get("result") or []
    items: list[BitrixLeadStatus] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        items.append(BitrixLeadStatus(
            status_id=str(r.get("STATUS_ID") or r.get("ID") or ""),
            name=str(r.get("NAME") or "").strip() or str(r.get("STATUS_ID") or ""),
            sort=int(r.get("SORT") or 0),
            color=str(r.get("COLOR") or ""),
        ))
    items.sort(key=lambda s: (s.sort, s.name))
    return items


async def _fetch_lead_statuses() -> list[BitrixLeadStatus]:
    return await _fetch_status_list("STATUS")


async def _fetch_lead_sources() -> list[BitrixLeadStatus]:
    return await _fetch_status_list("SOURCE")


@router.get("/leads/statuses", response_model=list[BitrixLeadStatus])
async def list_lead_statuses(user=Depends(get_current_user)) -> list[BitrixLeadStatus]:
    return await _fetch_lead_statuses()


@router.get("/leads/sources", response_model=list[BitrixLeadStatus])
async def list_lead_sources(user=Depends(get_current_user)) -> list[BitrixLeadStatus]:
    return await _fetch_lead_sources()


# ═══════════════════════════════════════════════════════════════════════════
# Лиды — список
# ═══════════════════════════════════════════════════════════════════════════

def _first_value(value: Any) -> str:
    if isinstance(value, list) and value:
        head = value[0]
        if isinstance(head, dict):
            return str(head.get("VALUE") or "").strip()
        return str(head).strip()
    if isinstance(value, str):
        return value.strip()
    return ""


@router.get("/leads", response_model=BitrixLeadsPage)
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(LEAD_PAGE_SIZE_MAX, ge=1, le=LEAD_PAGE_SIZE_MAX),
    status_id: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
    assigned_by_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=120),
    user=Depends(get_current_user),
) -> BitrixLeadsPage:
    filt: dict[str, Any] = {}
    if status_id:
        filt["STATUS_ID"] = status_id
    if source_id:
        filt["SOURCE_ID"] = source_id
    if assigned_by_id:
        filt["ASSIGNED_BY_ID"] = assigned_by_id
    df = _to_b24_iso(date_from)
    dt = _to_b24_iso(date_to, end_of_day=True)
    if df:
        filt[">=DATE_CREATE"] = df
    if dt:
        filt["<=DATE_CREATE"] = dt
    if search:
        filt["%TITLE"] = search.strip()

    start = (page - 1) * page_size
    data = await _b24(
        "crm.lead.list",
        {
            "filter": filt,
            "order": {"DATE_CREATE": "DESC"},
            "select": [
                "ID", "TITLE", "NAME", "LAST_NAME", "SECOND_NAME",
                "STATUS_ID", "SOURCE_ID", "OPPORTUNITY", "CURRENCY_ID",
                "PHONE", "EMAIL", "ASSIGNED_BY_ID", "DATE_CREATE", "DATE_MODIFY",
            ],
            "start": start,
        },
    )
    raw_items = (data.get("result") or [])[:page_size]
    total = int(data.get("total", len(raw_items)))

    statuses = {s.status_id: s.name for s in await _fetch_lead_statuses()}
    sources = {s.status_id: s.name for s in await _fetch_lead_sources()}
    users_map = await _fetch_users([str(r.get("ASSIGNED_BY_ID") or "") for r in raw_items])

    items: list[BitrixLead] = []
    for r in raw_items:
        sid = str(r.get("STATUS_ID") or "")
        src_id = str(r.get("SOURCE_ID") or "")
        uid = str(r.get("ASSIGNED_BY_ID") or "")
        items.append(BitrixLead(
            id=str(r.get("ID") or ""),
            title=str(r.get("TITLE") or "").strip(),
            name=str(r.get("NAME") or "").strip(),
            last_name=str(r.get("LAST_NAME") or "").strip(),
            second_name=str(r.get("SECOND_NAME") or "").strip(),
            status_id=sid,
            status_name=statuses.get(sid, sid),
            source_id=src_id,
            source_name=sources.get(src_id, src_id),
            opportunity=float(r.get("OPPORTUNITY") or 0) if r.get("OPPORTUNITY") not in (None, "") else 0.0,
            currency_id=str(r.get("CURRENCY_ID") or "").strip(),
            phone=_first_value(r.get("PHONE")),
            email=_first_value(r.get("EMAIL")),
            assigned_by_id=uid,
            assigned_by=users_map.get(uid, ""),
            created_at=_parse_b24_dt(r.get("DATE_CREATE")),
            modified_at=_parse_b24_dt(r.get("DATE_MODIFY")),
        ))

    if items:
        ids = [l.id for l in items if l.id]
        cursor = analyses.find(
            {"user_id": user["_id"], "kind": "lead", "lead.bitrix_lead_id": {"$in": ids}},
            {
                "_id": 1, "lead.bitrix_lead_id": 1, "lead.risk": 1,
                "status": 1, "scoring.meta.normalized_score": 1,
            },
        )
        by_lead: dict[str, dict] = {}
        async for d in cursor:
            by_lead[str((d.get("lead") or {}).get("bitrix_lead_id") or "")] = d
        for l in items:
            d = by_lead.get(l.id)
            if not d:
                continue
            l.analysis_id = str(d["_id"])
            l.analysis_status = str(d.get("status") or "")
            l.analysis_risk = str((d.get("lead") or {}).get("risk") or "")
            l.analysis_score = int(((d.get("scoring") or {}).get("meta") or {}).get("normalized_score") or 0)

    return BitrixLeadsPage(items=items, total=total, page=page, page_size=page_size)


# ═══════════════════════════════════════════════════════════════════════════
# Лиды — детали и таймлайн
# ═══════════════════════════════════════════════════════════════════════════

def _multi_field(value: Any) -> list[BitrixContactValue]:
    if not isinstance(value, list):
        return []
    out: list[BitrixContactValue] = []
    for entry in value:
        if isinstance(entry, dict):
            v = str(entry.get("VALUE") or "").strip()
            if not v:
                continue
            out.append(BitrixContactValue(value=v, kind=str(entry.get("VALUE_TYPE") or "")))
        elif isinstance(entry, str) and entry.strip():
            out.append(BitrixContactValue(value=entry.strip(), kind=""))
    return out


@router.get("/leads/{lead_id}", response_model=BitrixLeadDetail)
async def get_lead(lead_id: str, user=Depends(get_current_user)) -> BitrixLeadDetail:
    if not lead_id.strip().isdigit():
        raise HTTPException(status_code=400, detail="Некорректный ID лида")

    data = await _b24("crm.lead.get", {"id": lead_id})
    raw = data.get("result")
    if not raw:
        raise HTTPException(status_code=404, detail="Лид не найден")

    statuses = {s.status_id: s.name for s in await _fetch_lead_statuses()}
    assigned_id = str(raw.get("ASSIGNED_BY_ID") or "")
    created_by_id = str(raw.get("CREATED_BY_ID") or "")
    users_map = await _fetch_users([assigned_id, created_by_id])
    sid = str(raw.get("STATUS_ID") or "")

    return BitrixLeadDetail(
        id=str(raw.get("ID") or lead_id),
        bitrix_url=_lead_portal_url(str(raw.get("ID") or lead_id)),
        title=str(raw.get("TITLE") or "").strip(),
        name=str(raw.get("NAME") or "").strip(),
        last_name=str(raw.get("LAST_NAME") or "").strip(),
        second_name=str(raw.get("SECOND_NAME") or "").strip(),
        honorific=str(raw.get("HONORIFIC") or "").strip(),
        status_id=sid,
        status_name=statuses.get(sid, sid),
        source_id=str(raw.get("SOURCE_ID") or "").strip(),
        source_description=str(raw.get("SOURCE_DESCRIPTION") or "").strip(),
        opportunity=float(raw.get("OPPORTUNITY") or 0) if raw.get("OPPORTUNITY") not in (None, "") else 0.0,
        currency_id=str(raw.get("CURRENCY_ID") or "").strip(),
        assigned_by_id=assigned_id,
        assigned_by=users_map.get(assigned_id, ""),
        created_by_id=created_by_id,
        created_by=users_map.get(created_by_id, ""),
        company_title=str(raw.get("COMPANY_TITLE") or "").strip(),
        post=str(raw.get("POST") or "").strip(),
        address=str(raw.get("ADDRESS") or "").strip(),
        comments=str(raw.get("COMMENTS") or "").strip(),
        phones=_multi_field(raw.get("PHONE")),
        emails=_multi_field(raw.get("EMAIL")),
        webs=_multi_field(raw.get("WEB")),
        ims=_multi_field(raw.get("IM")),
        utm_source=str(raw.get("UTM_SOURCE") or "").strip(),
        utm_medium=str(raw.get("UTM_MEDIUM") or "").strip(),
        utm_campaign=str(raw.get("UTM_CAMPAIGN") or "").strip(),
        created_at=_parse_b24_dt(raw.get("DATE_CREATE")),
        modified_at=_parse_b24_dt(raw.get("DATE_MODIFY")),
    )


_ACTIVITY_TYPE_MAP = {1: "meeting", 2: "call", 3: "task", 4: "email", 6: "activity"}


@router.get("/leads/{lead_id}/activity", response_model=BitrixLeadActivity)
async def get_lead_activity(
    lead_id: str,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
) -> BitrixLeadActivity:
    if not lead_id.strip().isdigit():
        raise HTTPException(status_code=400, detail="Некорректный ID лида")

    df = _to_b24_iso(date_from)
    dt = _to_b24_iso(date_to, end_of_day=True)

    activity_filter: dict[str, Any] = {"OWNER_TYPE_ID": 1, "OWNER_ID": int(lead_id)}
    comment_filter: dict[str, Any] = {"ENTITY_ID": int(lead_id), "ENTITY_TYPE": "lead"}
    call_filter: dict[str, Any] = {"CRM_ENTITY_TYPE": "LEAD", "CRM_ENTITY_ID": lead_id}
    if df:
        activity_filter[">=CREATED"] = df
        comment_filter[">=CREATED"] = df
        call_filter[">=CALL_START_DATE"] = df
    if dt:
        activity_filter["<=CREATED"] = dt
        comment_filter["<=CREATED"] = dt
        call_filter["<=CALL_START_DATE"] = dt

    try:
        act_data = await _b24("crm.activity.list", {
            "filter": activity_filter,
            "order": {"CREATED": "DESC"},
            "select": [
                "ID", "TYPE_ID", "SUBJECT", "DESCRIPTION",
                "COMPLETED", "RESPONSIBLE_ID", "CREATED",
                "START_TIME", "END_TIME", "DIRECTION",
            ],
        })
        activities = act_data.get("result") or []
    except HTTPException:
        activities = []

    try:
        com_data = await _b24("crm.timeline.comment.list", {
            "filter": comment_filter, "order": {"CREATED": "DESC"},
        })
        comments = com_data.get("result") or []
    except HTTPException:
        comments = []

    try:
        call_data = await _b24("voximplant.statistic.get", {
            "FILTER": call_filter, "SORT": "CALL_START_DATE", "ORDER": "DESC",
        })
        call_rows = call_data.get("result") or []
    except HTTPException:
        call_rows = []

    user_ids: list[str] = []
    for a in activities:
        if isinstance(a, dict):
            user_ids.append(str(a.get("RESPONSIBLE_ID") or ""))
    for c in comments:
        if isinstance(c, dict):
            user_ids.append(str(c.get("AUTHOR_ID") or ""))
    for r in call_rows:
        if isinstance(r, dict):
            user_ids.append(str(r.get("PORTAL_USER_ID") or ""))
    users_map = await _fetch_users(user_ids)

    timeline: list[BitrixLeadTimelineEntry] = []
    for a in activities:
        if not isinstance(a, dict):
            continue
        try:
            type_id = int(a.get("TYPE_ID") or 0)
        except (TypeError, ValueError):
            type_id = 0
        if type_id == 2:  # звонки идут в отдельную секцию
            continue
        timeline.append(BitrixLeadTimelineEntry(
            id=str(a.get("ID") or ""),
            kind="activity",
            activity_type=_ACTIVITY_TYPE_MAP.get(type_id, "activity"),
            subject=str(a.get("SUBJECT") or "").strip(),
            text=str(a.get("DESCRIPTION") or "").strip(),
            author_id=str(a.get("RESPONSIBLE_ID") or ""),
            author=users_map.get(str(a.get("RESPONSIBLE_ID") or ""), ""),
            completed=str(a.get("COMPLETED") or "N").upper() == "Y",
            direction=str(a.get("DIRECTION") or ""),
            date=_parse_b24_dt(a.get("CREATED") or a.get("START_TIME")),
        ))
    for c in comments:
        if not isinstance(c, dict):
            continue
        author_id = str(c.get("AUTHOR_ID") or "")
        timeline.append(BitrixLeadTimelineEntry(
            id=str(c.get("ID") or ""),
            kind="comment",
            text=str(c.get("COMMENT") or "").strip(),
            author_id=author_id,
            author=users_map.get(author_id, ""),
            completed=True,
            date=_parse_b24_dt(c.get("CREATED")),
        ))
    timeline.sort(key=lambda e: e.date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    calls = [_normalize_call(r, users_map) for r in call_rows if isinstance(r, dict)]
    await _enrich_calls_with_analysis(user, calls)

    return BitrixLeadActivity(timeline=timeline, calls=calls)


# ═══════════════════════════════════════════════════════════════════════════
# Лиды — анализ (map-reduce)
# ═══════════════════════════════════════════════════════════════════════════

def _fmt_b24_dt(value: Any, fmt: str = "%d.%m.%Y %H:%M") -> str:
    dt = _parse_b24_dt(value)
    return dt.strftime(fmt) if dt else "—"


def _build_reduce_input(
    raw_lead: dict[str, Any],
    statuses_map: dict[str, str],
    sources_map: dict[str, str],
    call_refs: list[LeadCallRef],
    call_docs: list[Optional[dict]],
    comments: list[dict[str, Any]],
) -> str:
    sid = str(raw_lead.get("STATUS_ID") or "")
    src_id = str(raw_lead.get("SOURCE_ID") or "")
    created = _parse_b24_dt(raw_lead.get("DATE_CREATE"))
    days_old = f"{(datetime.now(timezone.utc) - created).days} дн." if created else ""

    meta_lines = [
        "ЛИД:",
        f"  ID: {raw_lead.get('ID') or '—'}",
        f"  Название: {(raw_lead.get('TITLE') or '').strip() or '—'}",
        f"  Статус: {statuses_map.get(sid, sid) or '—'}",
        f"  Источник: {sources_map.get(src_id, src_id) or '—'}",
    ]
    if raw_lead.get("OPPORTUNITY"):
        meta_lines.append(f"  Сумма: {raw_lead.get('OPPORTUNITY')} {raw_lead.get('CURRENCY_ID') or ''}".rstrip())
    if days_old:
        meta_lines.append(f"  Возраст лида: {days_old}")
    card_comment = (raw_lead.get("COMMENTS") or "").strip() if isinstance(raw_lead.get("COMMENTS"), str) else ""
    if card_comment:
        meta_lines.append(f"  Комментарий в карточке: {card_comment[:600]}")

    parts: list[str] = ["\n".join(meta_lines), ""]
    analyzed = [(r, d) for r, d in zip(call_refs, call_docs) if r.analyzed and d]
    skipped = [r for r in call_refs if not r.analyzed]

    if analyzed:
        parts.append(f"ЗВОНКИ ({len(call_refs)} шт, проанализировано {len(analyzed)} из {len(call_refs)}):")
        for r, d in analyzed[:12]:
            scoring = (d or {}).get("scoring") or {}
            meta = scoring.get("meta") or {}
            strengths = [str(s).strip() for s in (scoring.get("strengths") or []) if str(s).strip()]
            weaknesses = [str(s).strip() for s in (scoring.get("weaknesses") or []) if str(s).strip()]
            verdict = str(meta.get("verdict") or "").strip()
            snippet = ((d or {}).get("source_text") or "")[:600].strip()
            dt_label = r.date.strftime("%d.%m.%Y %H:%M") if r.date else "—"

            block = [f"[Звонок {r.call_id}] {dt_label} · {r.direction or '—'} · {r.duration}с · оценка {r.normalized_score}/100 ({r.grade or '—'})"]
            if verdict:
                block.append(f"  Резюме: {verdict}")
            if strengths:
                block.append("  Плюсы: " + "; ".join(strengths))
            if weaknesses:
                block.append("  Минусы: " + "; ".join(weaknesses))
            if snippet:
                block.append(f"  Начало транскрипта: {snippet}")
            parts.append("\n".join(block))
        if skipped:
            parts.append(f"(Пропущено: {len(skipped)} — без записи или с ошибкой анализа)")
        parts.append("")
    else:
        parts.append("ЗВОНКОВ С УСПЕШНЫМ АНАЛИЗОМ НЕТ.")
        if call_refs:
            parts.append(f"(Всего звонков: {len(call_refs)}, у всех нет записи или анализ не прошёл)")
        parts.append("")

    if comments:
        parts.append(f"КОММЕНТАРИИ ТАЙМЛАЙНА ({len(comments)} шт):")
        for c in comments[:40]:
            dt_label = _fmt_b24_dt(c.get("CREATED"), "%d.%m %H:%M")
            text = str(c.get("COMMENT") or "").strip().replace("\n", " ")[:500]
            if text:
                parts.append(f"  [{dt_label}] {text}")
    return "\n".join(parts)


async def _run_lead_analysis_bg(
    user: dict[str, Any],
    lead_id: str,
    raw_lead: dict[str, Any],
    raw_calls: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    force: bool,
) -> None:
    """Фон: дотранскрибируем звонки, делаем reduce, сохраняем в analyses kind=lead."""
    try:
        call_ids_sorted = sorted([str(r.get("ID") or "") for r in raw_calls if r.get("ID")])
        last_comment_id = max((str(c.get("ID") or "") for c in comments if c.get("ID")), default="")
        hasher = hashlib.sha256()
        hasher.update("|".join(call_ids_sorted).encode())
        hasher.update(b"::")
        hasher.update(last_comment_id.encode())
        hasher.update(b"::")
        hasher.update(str(raw_lead.get("STATUS_ID") or "").encode())
        hasher.update(b"::")
        hasher.update(str(raw_lead.get("DATE_MODIFY") or "").encode())
        input_hash = hasher.hexdigest()[:16]

        existing = await analyses.find_one({
            "user_id": user["_id"], "kind": "lead", "lead.bitrix_lead_id": lead_id,
        })
        if (existing and not force
                and (existing.get("lead") or {}).get("input_hash") == input_hash
                and existing.get("status") == "done"):
            await analyses.update_one(
                {"_id": existing["_id"]},
                {"$set": {"status": "done", "updated_at": datetime.now(timezone.utc), "error": ""}},
            )
            return

        users_map = await _fetch_users([str(r.get("PORTAL_USER_ID") or "") for r in raw_calls])

        call_refs: list[LeadCallRef] = []
        call_docs: list[Optional[dict]] = []
        for raw in raw_calls:
            call = _normalize_call(raw, users_map)
            doc, reason = await _ensure_call_analyzed(user, raw, users_map)
            ref = LeadCallRef(
                analysis_id=str(doc["_id"]) if doc else "",
                call_id=call.id,
                date=call.date,
                direction=call.direction,
                duration=call.duration,
                analyzed=bool(doc),
                skipped_reason="" if doc else reason,
            )
            if doc:
                meta = (doc.get("scoring") or {}).get("meta") or {}
                ref.normalized_score = int(meta.get("normalized_score") or 0)
                ref.grade = str(meta.get("grade") or "")
            call_refs.append(ref)
            call_docs.append(doc)

        statuses_map = {s.status_id: s.name for s in await _fetch_lead_statuses()}
        sources_map = {s.status_id: s.name for s in await _fetch_lead_sources()}
        reduce_input = _build_reduce_input(raw_lead, statuses_map, sources_map, call_refs, call_docs, comments)

        scoring, qualitative = await analyze_lead_aggregate(reduce_input)

        assigned_id = str(raw_lead.get("ASSIGNED_BY_ID") or "")
        manager_map = await _fetch_users([assigned_id])
        await svc.upsert_lead(
            user_id=user["_id"],
            bitrix_lead_id=lead_id,
            title=str(raw_lead.get("TITLE") or "").strip() or f"Лид #{lead_id}",
            date=_parse_b24_dt(raw_lead.get("DATE_CREATE")),
            manager=manager_map.get(assigned_id, ""),
            manager_id=assigned_id,
            status_id=str(raw_lead.get("STATUS_ID") or ""),
            status_name=statuses_map.get(str(raw_lead.get("STATUS_ID") or ""), ""),
            source_id=str(raw_lead.get("SOURCE_ID") or ""),
            source_name=sources_map.get(str(raw_lead.get("SOURCE_ID") or ""), ""),
            opportunity=float(raw_lead.get("OPPORTUNITY") or 0) if raw_lead.get("OPPORTUNITY") not in (None, "") else 0.0,
            currency=str(raw_lead.get("CURRENCY_ID") or ""),
            bitrix_url=_lead_portal_url(lead_id),
            scoring=scoring,
            qualitative=qualitative,
            call_refs=call_refs,
            comments_count=len(comments),
            input_hash=input_hash,
            source_text=reduce_input,
        )
    except Exception as exc:
        logger.exception("Фоновый анализ лида %s упал", lead_id)
        await analyses.update_one(
            {"user_id": user["_id"], "kind": "lead", "lead.bitrix_lead_id": lead_id},
            {
                "$set": {
                    "status": "failed", "error": str(exc)[:500],
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "user_id": user["_id"], "kind": "lead",
                    "lead": {"bitrix_lead_id": lead_id},
                    "created_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )


@router.post("/leads/{lead_id}/analyze", response_model=AnalysisOut)
async def analyze_lead(
    lead_id: str,
    force: bool = Query(False, description="Игнорировать кэш и пересчитать"),
    user=Depends(get_current_user),
) -> AnalysisOut:
    if not lead_id.strip().isdigit():
        raise HTTPException(status_code=400, detail="Некорректный ID лида")

    existing = await analyses.find_one({
        "user_id": user["_id"], "kind": "lead", "lead.bitrix_lead_id": lead_id,
    })
    if existing and existing.get("status") == "processing":
        return svc.doc_to_out(existing)

    lead_data = await _b24("crm.lead.get", {"id": lead_id})
    raw_lead = lead_data.get("result")
    if not raw_lead:
        raise HTTPException(status_code=404, detail="Лид не найден")

    call_data = await _b24("voximplant.statistic.get", {
        "FILTER": {"CRM_ENTITY_TYPE": "LEAD", "CRM_ENTITY_ID": lead_id},
        "SORT": "CALL_START_DATE", "ORDER": "ASC",
    })
    raw_calls = [r for r in (call_data.get("result") or []) if isinstance(r, dict)]

    try:
        com_data = await _b24("crm.timeline.comment.list", {
            "filter": {"ENTITY_ID": int(lead_id), "ENTITY_TYPE": "lead"},
            "order": {"CREATED": "ASC"},
        })
        comments = [c for c in (com_data.get("result") or []) if isinstance(c, dict)]
    except HTTPException:
        comments = []

    if not raw_calls and not comments:
        raise HTTPException(status_code=400, detail="По лиду нет звонков и комментариев — нечего анализировать.")

    now = datetime.now(timezone.utc)
    statuses_map = {s.status_id: s.name for s in await _fetch_lead_statuses()}
    await analyses.update_one(
        {"user_id": user["_id"], "kind": "lead", "lead.bitrix_lead_id": lead_id},
        {
            "$set": {
                "status": "processing",
                "title": str(raw_lead.get("TITLE") or "").strip() or f"Лид #{lead_id}",
                "date": _parse_b24_dt(raw_lead.get("DATE_CREATE")),
                "updated_at": now,
                "error": "",
                "lead.bitrix_lead_id": lead_id,
                "lead.status_id": str(raw_lead.get("STATUS_ID") or ""),
                "lead.status_name": statuses_map.get(str(raw_lead.get("STATUS_ID") or ""), ""),
                "lead.bitrix_url": _lead_portal_url(lead_id),
            },
            "$setOnInsert": {
                "user_id": user["_id"], "kind": "lead", "created_at": now,
            },
        },
        upsert=True,
    )

    asyncio.create_task(_run_lead_analysis_bg(user, lead_id, raw_lead, raw_calls, comments, force))

    fresh = await analyses.find_one({
        "user_id": user["_id"], "kind": "lead", "lead.bitrix_lead_id": lead_id,
    })
    return svc.doc_to_out(fresh)


@router.get("/leads/{lead_id}/analysis", response_model=AnalysisOut)
async def get_lead_analysis(lead_id: str, user=Depends(get_current_user)) -> AnalysisOut:
    if not lead_id.strip().isdigit():
        raise HTTPException(status_code=400, detail="Некорректный ID лида")
    doc = await analyses.find_one({
        "user_id": user["_id"], "kind": "lead", "lead.bitrix_lead_id": lead_id,
    })
    if not doc:
        raise HTTPException(status_code=404, detail="Анализ ещё не выполнен")
    return svc.doc_to_out(doc)
