"""Единый сервис над коллекцией `analyses`.

Все операции с анализами (создание для звонка/чата/лида, перечитка, удаление,
аналитика) проходят через этот модуль. Роутеры остаются тонкими.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from bson import ObjectId

from .. import scoring_card as sc
from ..database import analyses, audio_bucket
from ..models import (
    AnalysisOut,
    AnalyticsOverview,
    CallData,
    ChatData,
    CoachingTask,
    CriterionAverage,
    CriterionScore,
    DailyPoint,
    KindCount,
    LeadCallRef,
    LeadData,
    OperatorDailyStat,
    OperatorDetail,
    OperatorStat,
    Scoring,
    ScoringMeta,
    StopFactor,
)


# ═══════════════════════════════════════════════════════════════════════════
# Док ↔ модель
# ═══════════════════════════════════════════════════════════════════════════

def _scoring_from_doc(raw: Optional[dict]) -> Optional[Scoring]:
    if not raw:
        return None
    meta = raw.get("meta") or {}
    return Scoring(
        meta=ScoringMeta(
            verdict=str(meta.get("verdict") or ""),
            raw_score=int(meta.get("raw_score") or 0),
            max_raw_score=int(meta.get("max_raw_score") or sc.max_raw_score()),
            normalized_score=int(meta.get("normalized_score") or 0),
            grade=str(meta.get("grade") or ""),
        ),
        strengths=[str(x) for x in (raw.get("strengths") or [])],
        weaknesses=[str(x) for x in (raw.get("weaknesses") or [])],
        criteria_scores=[CriterionScore(**c) for c in (raw.get("criteria_scores") or []) if isinstance(c, dict)],
        stop_factors=[StopFactor(**s) for s in (raw.get("stop_factors") or []) if isinstance(s, dict)],
        coaching_tasks=[CoachingTask(**t) for t in (raw.get("coaching_tasks") or []) if isinstance(t, dict)],
        sentiment=str(raw.get("sentiment") or ""),
        topics=[str(x) for x in (raw.get("topics") or [])],
        summary=str(raw.get("summary") or ""),
    )


def doc_to_out(doc: dict) -> AnalysisOut:
    """Преобразование Mongo-документа в API-DTO."""
    call_raw = doc.get("call")
    chat_raw = doc.get("chat")
    lead_raw = doc.get("lead")

    call = CallData(**{k: v for k, v in call_raw.items() if k in CallData.model_fields}) if call_raw else None
    chat = ChatData(**{k: v for k, v in chat_raw.items() if k in ChatData.model_fields}) if chat_raw else None

    lead: Optional[LeadData] = None
    if lead_raw:
        refs_raw = lead_raw.get("call_refs") or []
        refs: list[LeadCallRef] = []
        for r in refs_raw:
            if isinstance(r, dict):
                try:
                    refs.append(LeadCallRef(**r))
                except Exception:
                    continue
        lead_kwargs = {k: v for k, v in lead_raw.items() if k in LeadData.model_fields and k != "call_refs"}
        lead = LeadData(**lead_kwargs, call_refs=refs)

    return AnalysisOut(
        id=str(doc["_id"]),
        kind=doc.get("kind", "call"),
        status=doc.get("status", "done"),
        title=str(doc.get("title") or ""),
        date=doc.get("date"),
        duration=int(doc.get("duration") or 0),
        manager=str(doc.get("manager") or ""),
        manager_id=str(doc.get("manager_id") or ""),
        source_text=str(doc.get("source_text") or ""),
        scoring=_scoring_from_doc(doc.get("scoring")),
        call=call,
        chat=chat,
        lead=lead,
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
        error=str(doc.get("error") or ""),
    )


def scoring_to_doc(scoring: Optional[Scoring]) -> Optional[dict]:
    return scoring.model_dump() if scoring else None


# ═══════════════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════════════

async def find_by_id(user_id: Any, analysis_id: str) -> Optional[dict]:
    try:
        oid = ObjectId(analysis_id)
    except Exception:
        return None
    return await analyses.find_one({"_id": oid, "user_id": user_id})


async def find_by_external(user_id: Any, kind: str, ext_field: str, ext_id: str) -> Optional[dict]:
    """ext_field: 'call.bitrix_call_id' | 'chat.bitrix_chat_id' | 'lead.bitrix_lead_id'."""
    return await analyses.find_one({"user_id": user_id, "kind": kind, ext_field: ext_id})


async def upsert_call(
    *,
    user_id: Any,
    bitrix_call_id: str,
    title: str,
    date: Optional[datetime],
    duration: int,
    phone: str,
    direction: str,
    manager: str,
    manager_id: str,
    record_url: str,
    text: str,
    scoring: Optional[Scoring],
    status: str = "done",
    audio_file_id: Any = None,
    audio_content_type: str = "",
    language: str = "",
    error: str = "",
) -> dict:
    now = datetime.now(timezone.utc)
    set_doc: dict = {
        "user_id": user_id,
        "kind": "call",
        "status": status,
        "title": title,
        "date": date,
        "duration": duration,
        "manager": manager,
        "manager_id": manager_id,
        "source_text": text,
        "scoring": scoring_to_doc(scoring),
        "call": CallData(
            bitrix_call_id=bitrix_call_id,
            phone=phone,
            direction=direction,
            record_url=record_url,
            has_audio=bool(audio_file_id),
            language=language,
        ).model_dump(),
        "error": error,
        "updated_at": now,
    }
    if audio_file_id is not None:
        set_doc["audio_file_id"] = audio_file_id
        set_doc["audio_content_type"] = audio_content_type or "audio/mpeg"

    await analyses.update_one(
        {"user_id": user_id, "kind": "call", "call.bitrix_call_id": bitrix_call_id},
        {"$set": set_doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return await analyses.find_one({
        "user_id": user_id, "kind": "call", "call.bitrix_call_id": bitrix_call_id,
    })


async def upsert_chat(
    *,
    user_id: Any,
    bitrix_chat_id: str,
    title: str,
    date: Optional[datetime],
    channel: str,
    client: str,
    subject: str,
    manager: str,
    manager_id: str,
    messages_count: int,
    text: str,
    scoring: Optional[Scoring],
    status: str = "done",
    error: str = "",
) -> dict:
    now = datetime.now(timezone.utc)
    await analyses.update_one(
        {"user_id": user_id, "kind": "chat", "chat.bitrix_chat_id": bitrix_chat_id},
        {
            "$set": {
                "user_id": user_id,
                "kind": "chat",
                "status": status,
                "title": title,
                "date": date,
                "duration": 0,
                "manager": manager,
                "manager_id": manager_id,
                "source_text": text,
                "scoring": scoring_to_doc(scoring),
                "chat": ChatData(
                    bitrix_chat_id=bitrix_chat_id,
                    channel=channel,
                    client=client,
                    subject=subject,
                    messages_count=messages_count,
                ).model_dump(),
                "error": error,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return await analyses.find_one({
        "user_id": user_id, "kind": "chat", "chat.bitrix_chat_id": bitrix_chat_id,
    })


async def upsert_lead(
    *,
    user_id: Any,
    bitrix_lead_id: str,
    title: str,
    date: Optional[datetime],
    manager: str,
    manager_id: str,
    status_id: str,
    status_name: str,
    source_id: str,
    source_name: str,
    opportunity: float,
    currency: str,
    bitrix_url: str,
    scoring: Optional[Scoring],
    qualitative: dict,
    call_refs: list[LeadCallRef],
    comments_count: int,
    input_hash: str,
    source_text: str,
    status: str = "done",
    error: str = "",
) -> dict:
    now = datetime.now(timezone.utc)
    lead = LeadData(
        bitrix_lead_id=bitrix_lead_id,
        title=title,
        status_id=status_id,
        status_name=status_name,
        source_id=source_id,
        source_name=source_name,
        opportunity=opportunity,
        currency=currency,
        bitrix_url=bitrix_url,
        summary=str(qualitative.get("summary") or ""),
        client_request=str(qualitative.get("client_request") or ""),
        objections=list(qualitative.get("objections") or []),
        risk=str(qualitative.get("risk") or "low"),
        risk_reason=str(qualitative.get("risk_reason") or ""),
        next_step=str(qualitative.get("next_step") or ""),
        calls_count=len(call_refs),
        comments_count=comments_count,
        call_refs=call_refs,
        input_hash=input_hash,
    ).model_dump()

    await analyses.update_one(
        {"user_id": user_id, "kind": "lead", "lead.bitrix_lead_id": bitrix_lead_id},
        {
            "$set": {
                "user_id": user_id,
                "kind": "lead",
                "status": status,
                "title": title,
                "date": date,
                "duration": 0,
                "manager": manager,
                "manager_id": manager_id,
                "source_text": source_text,
                "scoring": scoring_to_doc(scoring),
                "lead": lead,
                "error": error,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return await analyses.find_one({
        "user_id": user_id, "kind": "lead", "lead.bitrix_lead_id": bitrix_lead_id,
    })


async def set_status(user_id: Any, analysis_id: str, status: str, *, error: str = "") -> None:
    try:
        oid = ObjectId(analysis_id)
    except Exception:
        return
    await analyses.update_one(
        {"_id": oid, "user_id": user_id},
        {"$set": {"status": status, "error": error, "updated_at": datetime.now(timezone.utc)}},
    )


async def delete(user_id: Any, analysis_id: str) -> bool:
    try:
        oid = ObjectId(analysis_id)
    except Exception:
        return False
    doc = await analyses.find_one({"_id": oid, "user_id": user_id})
    if not doc:
        return False
    audio_id = doc.get("audio_file_id")
    if audio_id is not None:
        try:
            await audio_bucket.delete(audio_id)
        except Exception:
            pass
    await analyses.delete_one({"_id": oid, "user_id": user_id})
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Список и фильтры
# ═══════════════════════════════════════════════════════════════════════════

def _match(
    user_id: Any,
    *,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    manager_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    q: dict = {"user_id": user_id}
    if kind and kind != "all":
        q["kind"] = kind
    if status:
        q["status"] = status
    if manager_id is not None:
        q["manager_id"] = manager_id
    if date_from or date_to:
        rng: dict = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        q["date"] = rng
    return q


async def list_analyses(
    user_id: Any,
    *,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    manager_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 100,
    skip: int = 0,
) -> list[AnalysisOut]:
    q = _match(user_id, kind=kind, status=status, manager_id=manager_id,
               date_from=date_from, date_to=date_to)
    cursor = analyses.find(q).sort("date", -1).skip(skip).limit(limit)
    return [doc_to_out(doc) async for doc in cursor]


async def count_analyses(
    user_id: Any,
    *,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    manager_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> int:
    q = _match(user_id, kind=kind, status=status, manager_id=manager_id,
               date_from=date_from, date_to=date_to)
    return await analyses.count_documents(q)


# ═══════════════════════════════════════════════════════════════════════════
# Аналитика
# ═══════════════════════════════════════════════════════════════════════════

async def overview(
    user_id: Any,
    *,
    kind: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> AnalyticsOverview:
    base = _match(user_id, kind=kind, status="done", date_from=date_from, date_to=date_to)

    # Сводка
    summary_pipeline = [
        {"$match": base},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "analyzed": {"$sum": {"$cond": [{"$ifNull": ["$scoring", False]}, 1, 0]}},
            "avg_score": {"$avg": "$scoring.meta.normalized_score"},
            "total_duration": {"$sum": {"$ifNull": ["$duration", 0]}},
        }},
    ]
    summary_docs = await analyses.aggregate(summary_pipeline).to_list(length=1)
    summary = summary_docs[0] if summary_docs else None

    # Breakdown по kind
    kind_pipeline = [
        {"$match": _match(user_id, status="done", date_from=date_from, date_to=date_to)},
        {"$group": {"_id": "$kind", "count": {"$sum": 1}}},
    ]
    by_kind = KindCount()
    async for row in analyses.aggregate(kind_pipeline):
        k = str(row.get("_id") or "")
        cnt = int(row.get("count") or 0)
        if k == "call":
            by_kind.calls = cnt
        elif k == "lead":
            by_kind.leads = cnt
        elif k == "chat":
            by_kind.chats = cnt

    # Тональность
    sentiment_pipeline = [
        {"$match": base},
        {"$group": {"_id": "$scoring.sentiment", "count": {"$sum": 1}}},
    ]
    sentiment: dict = {}
    async for row in analyses.aggregate(sentiment_pipeline):
        key = str(row.get("_id") or "unknown") or "unknown"
        sentiment[key] = int(row.get("count") or 0)

    # Распределение по grade
    grade_pipeline = [
        {"$match": base},
        {"$group": {"_id": "$scoring.meta.grade", "count": {"$sum": 1}}},
    ]
    grades: dict = {}
    async for row in analyses.aggregate(grade_pipeline):
        key = str(row.get("_id") or "—") or "—"
        grades[key] = int(row.get("count") or 0)

    # Средние по критериям
    criteria_pipeline = [
        {"$match": base},
        {"$unwind": "$scoring.criteria_scores"},
        {"$group": {
            "_id": "$scoring.criteria_scores.id",
            "name": {"$first": "$scoring.criteria_scores.name"},
            "category_id": {"$first": "$scoring.criteria_scores.category_id"},
            "category_name": {"$first": "$scoring.criteria_scores.category_name"},
            "max_score": {"$first": "$scoring.criteria_scores.max_score"},
            "avg_score": {"$avg": "$scoring.criteria_scores.score"},
            "samples": {"$sum": 1},
        }},
        {"$sort": {"avg_score": -1}},
    ]
    criteria: list[CriterionAverage] = []
    async for row in analyses.aggregate(criteria_pipeline):
        avg = row.get("avg_score") or 0
        criteria.append(CriterionAverage(
            id=str(row.get("_id") or ""),
            name=str(row.get("name") or ""),
            category_id=str(row.get("category_id") or ""),
            category_name=str(row.get("category_name") or ""),
            avg_score=round(float(avg), 1),
            max_score=int(row.get("max_score") or 0),
            samples=int(row.get("samples") or 0),
        ))

    # Операторы
    operators = await _operators(user_id, kind=kind, status="done",
                                 date_from=date_from, date_to=date_to)

    # Ежедневная динамика
    daily_pipeline = [
        {"$match": base},
        {"$match": {"date": {"$ne": None}}},
        {"$group": {
            "_id": {
                "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date"}},
                "kind": "$kind",
            },
            "count": {"$sum": 1},
            "avg_score": {"$avg": "$scoring.meta.normalized_score"},
        }},
        {"$sort": {"_id.date": 1}},
    ]
    daily_map: dict[str, DailyPoint] = {}
    async for row in analyses.aggregate(daily_pipeline):
        ident = row.get("_id") or {}
        date = str(ident.get("date") or "")
        if not date:
            continue
        k = str(ident.get("kind") or "")
        point = daily_map.setdefault(date, DailyPoint(date=date))
        cnt = int(row.get("count") or 0)
        point.total += cnt
        if k == "call":
            point.calls += cnt
        elif k == "lead":
            point.leads += cnt
        elif k == "chat":
            point.chats += cnt
        # средневзвешенно вынесем ниже; пока сохраним последнее avg
        point.avg_score = (
            row.get("avg_score")
            if point.avg_score is None
            else (point.avg_score + (row.get("avg_score") or 0)) / 2
        )
    daily = sorted(daily_map.values(), key=lambda p: p.date)
    for p in daily:
        if p.avg_score is not None:
            p.avg_score = round(float(p.avg_score), 1)

    if summary:
        avg = summary.get("avg_score")
        return AnalyticsOverview(
            total=int(summary.get("total") or 0),
            analyzed=int(summary.get("analyzed") or 0),
            by_kind=by_kind,
            avg_score=round(float(avg), 1) if avg is not None else None,
            total_duration=int(summary.get("total_duration") or 0),
            sentiment_breakdown=sentiment,
            grade_breakdown=grades,
            criteria=criteria,
            operators=operators,
            daily=daily,
        )
    return AnalyticsOverview(
        by_kind=by_kind,
        sentiment_breakdown=sentiment,
        grade_breakdown=grades,
        criteria=criteria,
        operators=operators,
        daily=daily,
    )


async def _operators(
    user_id: Any,
    *,
    kind: Optional[str] = None,
    status: Optional[str] = "done",
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> list[OperatorStat]:
    base = _match(user_id, kind=kind, status=status, date_from=date_from, date_to=date_to)
    pipeline = [
        {"$match": base},
        {"$group": {
            "_id": {"id": {"$ifNull": ["$manager_id", "—"]}, "name": {"$ifNull": ["$manager", ""]}},
            "total": {"$sum": 1},
            "calls": {"$sum": {"$cond": [{"$eq": ["$kind", "call"]}, 1, 0]}},
            "leads": {"$sum": {"$cond": [{"$eq": ["$kind", "lead"]}, 1, 0]}},
            "chats": {"$sum": {"$cond": [{"$eq": ["$kind", "chat"]}, 1, 0]}},
            "analyzed": {"$sum": {"$cond": [{"$ifNull": ["$scoring", False]}, 1, 0]}},
            "avg_score": {"$avg": "$scoring.meta.normalized_score"},
            "total_duration": {"$sum": {"$ifNull": ["$duration", 0]}},
            "last_activity_at": {"$max": "$date"},
        }},
        {"$sort": {"avg_score": -1, "total": -1}},
    ]
    out: list[OperatorStat] = []
    async for row in analyses.aggregate(pipeline):
        ident = row.get("_id") or {}
        avg = row.get("avg_score")
        out.append(OperatorStat(
            manager_id=str(ident.get("id") or "—") or "—",
            manager=str(ident.get("name") or "Без имени"),
            total=int(row.get("total") or 0),
            calls=int(row.get("calls") or 0),
            leads=int(row.get("leads") or 0),
            chats=int(row.get("chats") or 0),
            analyzed=int(row.get("analyzed") or 0),
            avg_score=round(float(avg), 1) if avg is not None else None,
            total_duration=int(row.get("total_duration") or 0),
            last_activity_at=row.get("last_activity_at"),
        ))
    return out


async def operators(user_id: Any) -> list[OperatorStat]:
    return await _operators(user_id, status="done")


async def operator_detail(user_id: Any, manager_id: str, days: int) -> OperatorDetail:
    period_from = datetime.now(timezone.utc) - timedelta(days=days)
    manager_filter = manager_id if manager_id != "—" else {"$in": [None, "", "—"]}

    # Шапка — общая статистика за всё время
    head_match = {"user_id": user_id, "status": "done", "manager_id": manager_filter}
    head_pipeline = [
        {"$match": head_match},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "calls": {"$sum": {"$cond": [{"$eq": ["$kind", "call"]}, 1, 0]}},
            "leads": {"$sum": {"$cond": [{"$eq": ["$kind", "lead"]}, 1, 0]}},
            "chats": {"$sum": {"$cond": [{"$eq": ["$kind", "chat"]}, 1, 0]}},
            "analyzed": {"$sum": {"$cond": [{"$ifNull": ["$scoring", False]}, 1, 0]}},
            "avg_score": {"$avg": "$scoring.meta.normalized_score"},
            "total_duration": {"$sum": {"$ifNull": ["$duration", 0]}},
            "last_activity_at": {"$max": "$date"},
            "name": {"$last": "$manager"},
        }},
    ]
    head_docs = await analyses.aggregate(head_pipeline).to_list(length=1)
    head = head_docs[0] if head_docs else {}
    manager_name = str(head.get("name") or "Без имени") if head else "Без имени"
    avg_total = head.get("avg_score") if head else None

    stats = OperatorStat(
        manager_id=manager_id,
        manager=manager_name,
        total=int(head.get("total") or 0) if head else 0,
        calls=int(head.get("calls") or 0) if head else 0,
        leads=int(head.get("leads") or 0) if head else 0,
        chats=int(head.get("chats") or 0) if head else 0,
        analyzed=int(head.get("analyzed") or 0) if head else 0,
        avg_score=round(float(avg_total), 1) if avg_total is not None else None,
        total_duration=int(head.get("total_duration") or 0) if head else 0,
        last_activity_at=head.get("last_activity_at") if head else None,
    )

    # Окно — daily-разбивка + список записей
    period_match = {**head_match, "date": {"$gte": period_from}}
    daily_pipeline = [
        {"$match": period_match},
        {"$group": {
            "_id": {
                "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date"}},
                "kind": "$kind",
            },
            "count": {"$sum": 1},
            "avg_score": {"$avg": "$scoring.meta.normalized_score"},
            "total_duration": {"$sum": {"$ifNull": ["$duration", 0]}},
        }},
        {"$sort": {"_id.date": 1}},
    ]
    daily_map: dict[str, OperatorDailyStat] = {}
    async for row in analyses.aggregate(daily_pipeline):
        ident = row.get("_id") or {}
        date = str(ident.get("date") or "")
        if not date:
            continue
        k = str(ident.get("kind") or "")
        point = daily_map.setdefault(date, OperatorDailyStat(date=date, total=0))
        cnt = int(row.get("count") or 0)
        point.total += cnt
        if k == "call":
            point.calls += cnt
        elif k == "lead":
            point.leads += cnt
        elif k == "chat":
            point.chats += cnt
        point.total_duration += int(row.get("total_duration") or 0)
        point.avg_score = row.get("avg_score") if point.avg_score is None else (
            (point.avg_score + (row.get("avg_score") or 0)) / 2
        )
    daily = sorted(daily_map.values(), key=lambda p: p.date)
    for p in daily:
        if p.avg_score is not None:
            p.avg_score = round(float(p.avg_score), 1)

    cursor = analyses.find(period_match).sort("date", -1).limit(200)
    items = [doc_to_out(doc) async for doc in cursor]

    return OperatorDetail(
        manager_id=manager_id,
        manager=manager_name,
        period_days=days,
        stats=stats,
        daily=daily,
        analyses=items,
    )
