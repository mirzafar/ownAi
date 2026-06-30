"""Analytics — тонкая обёртка над analysis_service.

Все запросы фильтруют по `kind`: all (по умолчанию) | call | lead | chat.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..models import AnalyticsOverview, OperatorDetail, OperatorStat
from ..services import analysis_service as svc

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Bad date: {value}")


@router.get("/overview", response_model=AnalyticsOverview)
async def overview(
    kind: Optional[str] = Query(None, description="all | call | lead | chat"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user=Depends(get_current_user),
) -> AnalyticsOverview:
    return await svc.overview(
        user["_id"],
        kind=kind,
        date_from=_parse_dt(date_from),
        date_to=_parse_dt(date_to),
    )


@router.get("/operators", response_model=List[OperatorStat])
async def operators(user=Depends(get_current_user)) -> List[OperatorStat]:
    return await svc.operators(user["_id"])


@router.get("/operators/{manager_id}", response_model=OperatorDetail)
async def operator_detail(
    manager_id: str,
    days: int = Query(5, ge=1, le=90),
    user=Depends(get_current_user),
) -> OperatorDetail:
    return await svc.operator_detail(user["_id"], manager_id, days)
