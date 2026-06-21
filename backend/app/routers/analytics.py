from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..database import transcriptions
from ..models import (
    AnalyticsOverview,
    CriterionAverage,
    OperatorStat,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Bad date: {value}")


def _date_match(user_id: Any, date_from: Optional[datetime], date_to: Optional[datetime]) -> dict:
    match: dict = {
        "user_id": user_id,
        "source": "bitrix_call",
        "status": "done",
    }
    if date_from or date_to:
        rng: dict = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        match["bitrix_call_date"] = rng
    return match


@router.get("/overview", response_model=AnalyticsOverview)
async def overview(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
) -> AnalyticsOverview:
    df = _parse_dt(date_from)
    dt = _parse_dt(date_to)
    match = _date_match(user["_id"], df, dt)

    # Общая сводка
    summary_pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": None,
                "total_calls": {"$sum": 1},
                "analyzed": {
                    "$sum": {
                        "$cond": [{"$ifNull": ["$sales_analysis", False]}, 1, 0],
                    }
                },
                "avg_score": {"$avg": "$sales_analysis.meta.total_score"},
                "total_duration": {"$sum": {"$ifNull": ["$duration", 0]}},
            }
        },
    ]
    summary_docs = await transcriptions.aggregate(summary_pipeline).to_list(length=1)
    summary_doc = summary_docs[0] if summary_docs else None

    # Sentiment breakdown
    sentiment_pipeline = [
        {"$match": match},
        {"$group": {"_id": "$analysis.sentiment", "count": {"$sum": 1}}},
    ]
    sentiment: dict = {}
    async for row in transcriptions.aggregate(sentiment_pipeline):
        key = row.get("_id") or "unknown"
        sentiment[str(key)] = int(row.get("count") or 0)

    # Средние по критериям
    criteria_pipeline = [
        {"$match": match},
        {"$unwind": "$sales_analysis.criteria_scores"},
        {
            "$group": {
                "_id": "$sales_analysis.criteria_scores.criterion_id",
                "criterion_name": {
                    "$first": "$sales_analysis.criteria_scores.criterion_name"
                },
                "avg_score": {"$avg": "$sales_analysis.criteria_scores.score"},
                "samples": {"$sum": 1},
            }
        },
        {"$sort": {"avg_score": -1}},
    ]
    criteria: list[CriterionAverage] = []
    async for row in transcriptions.aggregate(criteria_pipeline):
        criteria.append(
            CriterionAverage(
                criterion_id=str(row.get("_id") or "unknown"),
                criterion_name=str(row.get("criterion_name") or row.get("_id") or ""),
                avg_score=round(float(row.get("avg_score") or 0), 1),
                samples=int(row.get("samples") or 0),
            )
        )

    # Операторы
    op_pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": {
                    "id": {"$ifNull": ["$bitrix_manager_id", "—"]},
                    "name": {"$ifNull": ["$bitrix_manager", ""]},
                },
                "calls": {"$sum": 1},
                "analyzed": {
                    "$sum": {
                        "$cond": [{"$ifNull": ["$sales_analysis", False]}, 1, 0],
                    }
                },
                "avg_score": {"$avg": "$sales_analysis.meta.total_score"},
                "total_duration": {"$sum": {"$ifNull": ["$duration", 0]}},
                "last_call_at": {"$max": "$bitrix_call_date"},
            }
        },
        {"$sort": {"avg_score": -1, "calls": -1}},
    ]
    operators: list[OperatorStat] = []
    async for row in transcriptions.aggregate(op_pipeline):
        ident = row.get("_id") or {}
        avg = row.get("avg_score")
        operators.append(
            OperatorStat(
                manager_id=str(ident.get("id") or "—") or "—",
                manager=str(ident.get("name") or "Без имени"),
                calls=int(row.get("calls") or 0),
                analyzed=int(row.get("analyzed") or 0),
                avg_score=round(float(avg), 1) if avg is not None else None,
                total_duration=int(row.get("total_duration") or 0),
                last_call_at=row.get("last_call_at"),
            )
        )

    # Дневная динамика
    daily_pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$bitrix_call_date",
                    }
                },
                "calls": {"$sum": 1},
                "avg_score": {"$avg": "$sales_analysis.meta.total_score"},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    daily: list[dict] = []
    async for row in transcriptions.aggregate(daily_pipeline):
        if not row.get("_id"):
            continue
        avg = row.get("avg_score")
        daily.append(
            {
                "date": row["_id"],
                "calls": int(row.get("calls") or 0),
                "avg_score": round(float(avg), 1) if avg is not None else None,
            }
        )

    if summary_doc:
        avg_score = summary_doc.get("avg_score")
        return AnalyticsOverview(
            total_calls=int(summary_doc.get("total_calls") or 0),
            analyzed=int(summary_doc.get("analyzed") or 0),
            avg_score=round(float(avg_score), 1) if avg_score is not None else None,
            total_duration=int(summary_doc.get("total_duration") or 0),
            sentiment_breakdown=sentiment,
            criteria=criteria,
            operators=operators,
            daily=daily,
        )

    return AnalyticsOverview(
        total_calls=0,
        analyzed=0,
        avg_score=None,
        total_duration=0,
        sentiment_breakdown=sentiment,
        criteria=criteria,
        operators=operators,
        daily=daily,
    )
