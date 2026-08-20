"""Чтение аналитики по сменам статусов лидов из коллекции
`lead_status_events` (наполняется cron-синком lead_status_sync).

Метрика: за период по оператору — сколько уникальных лидов дошло до каждого
статуса (и сколько всего переходов). Создание лида (type_id=1) исключаем.
"""

from datetime import date
from typing import Optional

from ..database import lead_status_events
from ..models import LeadStatusAnalytics, LeadStatusBucket, LeadStatusTransition


def _operator_match(manager_id: str):
    if manager_id in ("—", "", "null"):
        return {"$in": ["", None, "—"]}
    return manager_id


async def operator_lead_status(
    manager_id: str,
    date_from: Optional[str],
    date_to: Optional[str],
) -> LeadStatusAnalytics:
    today = date.today().isoformat()
    date_from = date_from or today
    date_to = date_to or date_from

    match = {
        "operator_id": _operator_match(manager_id),
        "day": {"$gte": date_from, "$lte": date_to},
        "is_creation": {"$ne": True},   # только реальные смены статуса
    }

    # Разбивка по статусам: уникальные лиды + количество переходов.
    by_status_pipeline = [
        {"$match": match},
        {"$group": {
            "_id": "$to_status_id",
            "status_name": {"$first": "$to_status_name"},
            "semantic": {"$first": "$semantic"},
            "leads_set": {"$addToSet": "$lead_id"},
            "changes": {"$sum": 1},
        }},
        {"$project": {
            "status_name": 1,
            "semantic": 1,
            "changes": 1,
            "leads": {"$size": "$leads_set"},
        }},
        {"$sort": {"changes": -1}},
    ]
    by_status: list[LeadStatusBucket] = []
    async for row in lead_status_events.aggregate(by_status_pipeline):
        by_status.append(LeadStatusBucket(
            status_id=str(row.get("_id") or ""),
            status_name=str(row.get("status_name") or row.get("_id") or ""),
            semantic=str(row.get("semantic") or ""),
            leads=int(row.get("leads") or 0),
            changes=int(row.get("changes") or 0),
        ))

    # Итоги: уникальные лиды и всего переходов за период.
    totals_pipeline = [
        {"$match": match},
        {"$group": {
            "_id": None,
            "leads_set": {"$addToSet": "$lead_id"},
            "changes": {"$sum": 1},
            "operator_name": {"$last": "$operator_name"},
        }},
        {"$project": {
            "changes": 1,
            "operator_name": 1,
            "leads": {"$size": "$leads_set"},
        }},
    ]
    totals = await lead_status_events.aggregate(totals_pipeline).to_list(length=1)
    head = totals[0] if totals else {}

    # Детализация переходов (последние 300).
    transitions: list[LeadStatusTransition] = []
    cursor = lead_status_events.find(match).sort("changed_at", -1).limit(300)
    async for d in cursor:
        transitions.append(LeadStatusTransition(
            lead_id=str(d.get("lead_id") or ""),
            from_status_name=str(d.get("from_status_name") or ""),
            to_status_name=str(d.get("to_status_name") or ""),
            changed_at=d.get("changed_at"),
        ))

    return LeadStatusAnalytics(
        manager_id=manager_id,
        manager=str(head.get("operator_name") or ""),
        date_from=date_from,
        date_to=date_to,
        total_leads=int(head.get("leads") or 0),
        total_changes=int(head.get("changes") or 0),
        by_status=by_status,
        transitions=transitions,
    )
