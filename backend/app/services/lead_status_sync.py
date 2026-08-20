"""Синхронизация истории смены статусов лидов из Bitrix в коллекцию
`lead_status_events`.

Источник — crm.stagehistory.list (entityTypeId=1). Каждая запись это
«лид вошёл в статус X в момент T». Чтобы получить «с какого статуса», берём
статус предыдущей записи того же лида, поэтому подтягиваем полную историю
по лидам, которые двигались в окне.

«Кто нажал» в истории Bitrix нет — оператора берём как текущего
ответственного за лид (ASSIGNED_BY_ID).

Идемпотентность: `_id` документа = ID записи истории Bitrix, поэтому
повторный прогон за тот же период не создаёт дублей (bulk upsert).

Запускается по cron через backend/sync_lead_status.py.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from pymongo import UpdateOne

from ..database import lead_status_events
from ..routers.bitrix import _b24, _fetch_lead_statuses, _fetch_users, _parse_b24_dt

logger = logging.getLogger(__name__)

# TYPE_ID=1 — создание лида (вход в первый статус), не считаем «сменой статуса»,
# но храним для полноты и возможной статистики по новым лидам.
CREATION_TYPE = "1"
SEMANTIC = {"P": "в работе", "S": "успех", "F": "провал"}


def _items(data: dict[str, Any]) -> list[dict]:
    result = data.get("result")
    if isinstance(result, dict):
        return result.get("items") or []
    if isinstance(result, list):
        return result
    return []


async def _fetch_stagehistory(filt: dict[str, Any]) -> list[dict]:
    """Полная выгрузка crm.stagehistory.list (entityTypeId=1) с пагинацией."""
    out: list[dict] = []
    start = 0
    while True:
        data = await _b24("crm.stagehistory.list", {
            "entityTypeId": 1,
            "order": {"OWNER_ID": "ASC", "ID": "ASC"},
            "filter": filt,
            "select": ["ID", "TYPE_ID", "OWNER_ID", "CREATED_TIME", "STATUS_ID", "STATUS_SEMANTIC_ID"],
            "start": start,
        })
        batch = _items(data)
        out.extend(batch)
        total = data.get("total")
        if not batch or (total is not None and len(out) >= total):
            break
        start += 50
    return out


async def _assigned_operators(owner_ids: list[str]) -> dict[str, str]:
    """Лид -> ASSIGNED_BY_ID (текущий ответственный)."""
    assigned: dict[str, str] = {}
    for i in range(0, len(owner_ids), 50):
        chunk = owner_ids[i:i + 50]
        data = await _b24("crm.lead.list", {
            "filter": {"ID": chunk},
            "select": ["ID", "ASSIGNED_BY_ID"],
        })
        for r in (data.get("result") or []):
            assigned[str(r.get("ID"))] = str(r.get("ASSIGNED_BY_ID") or "")
    return assigned


async def sync_range(date_from: str, date_to: str) -> dict[str, int]:
    """Синхронизирует переходы статусов за [date_from; date_to] (YYYY-MM-DD).

    Возвращает статистику прогона.
    """
    logger.info("Синк истории статусов лидов: %s .. %s", date_from, date_to)

    window = await _fetch_stagehistory({
        ">=CREATED_TIME": f"{date_from}T00:00:00",
        "<=CREATED_TIME": f"{date_to}T23:59:59",
    })
    if not window:
        logger.info("Нет записей истории за период")
        return {"fetched": 0, "written": 0, "leads": 0}

    owner_ids = list({str(e["OWNER_ID"]) for e in window if e.get("OWNER_ID")})
    window_ids = {str(e["ID"]) for e in window}

    # Полная история этих лидов — чтобы знать «с какого статуса».
    history: list[dict] = []
    for i in range(0, len(owner_ids), 50):
        history.extend(await _fetch_stagehistory({"OWNER_ID": owner_ids[i:i + 50]}))

    by_lead: dict[str, list[dict]] = {}
    for h in history:
        by_lead.setdefault(str(h["OWNER_ID"]), []).append(h)
    for lst in by_lead.values():
        lst.sort(key=lambda r: int(r["ID"]))

    # Справочники: статусы + операторы.
    status_list = await _fetch_lead_statuses()
    status_names = {s.status_id: s.name for s in status_list}
    assigned_by = await _assigned_operators(owner_ids)
    user_names = await _fetch_users([v for v in assigned_by.values() if v])

    def sname(sid: Optional[str]) -> str:
        return status_names.get(str(sid), str(sid or ""))

    ops: list[UpdateOne] = []
    for lead_id, records in by_lead.items():
        op_id = assigned_by.get(lead_id, "")
        op_name = user_names.get(op_id, "")
        prev_status: Optional[str] = None
        for rec in records:
            rec_id = str(rec["ID"])
            if rec_id in window_ids:
                to_status = str(rec.get("STATUS_ID") or "")
                changed_at = _parse_b24_dt(rec.get("CREATED_TIME"))
                type_id = str(rec.get("TYPE_ID") or "")
                sem = str(rec.get("STATUS_SEMANTIC_ID") or "")
                doc = {
                    "lead_id": lead_id,
                    "from_status_id": prev_status or "",
                    "from_status_name": sname(prev_status) if prev_status else "",
                    "to_status_id": to_status,
                    "to_status_name": sname(to_status),
                    "semantic": sem,
                    "semantic_label": SEMANTIC.get(sem, ""),
                    "type_id": type_id,
                    "is_creation": type_id == CREATION_TYPE,
                    "operator_id": op_id,
                    "operator_name": op_name,
                    "changed_at": changed_at,
                    "day": changed_at.date().isoformat() if changed_at else date_from,
                    "synced_at": datetime.utcnow(),
                }
                ops.append(UpdateOne({"_id": int(rec_id)}, {"$set": doc}, upsert=True))
            prev_status = rec.get("STATUS_ID")

    written = 0
    if ops:
        res = await lead_status_events.bulk_write(ops, ordered=False)
        written = (res.upserted_count or 0) + (res.modified_count or 0)

    stats = {"fetched": len(window), "written": written, "leads": len(owner_ids)}
    logger.info("Синк завершён: %s", stats)
    return stats
