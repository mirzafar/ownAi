"""Тест: события смены статуса лидов за сегодня в формате откуда -> куда.

Источник — crm.stagehistory.list (entityTypeId=1 = лиды). Каждая запись это
"лид вошёл в статус X в момент T". Чтобы получить "с какого статуса", берём
статус предыдущей записи того же лида — поэтому тянем полную историю по лидам,
которые двигались сегодня, и выстраиваем цепочку.

"Кто нажал" в истории нет — оператора берём как текущего ответственного (ASSIGNED_BY_ID).

Запуск:  pipenv run python test.py
"""

import httpx
from datetime import datetime

from app.config import settings

BASE = settings.bitrix_webhook_url.strip()
if not BASE.endswith("/"):
    BASE += "/"


def b24(method: str, payload: dict) -> dict:
    resp = httpx.post(f"{BASE}{method}.json", json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"{method}: {data.get('error_description') or data['error']}")
    return data


def stagehistory_items(data: dict) -> list:
    result = data.get("result")
    if isinstance(result, dict):
        return result.get("items") or []
    if isinstance(result, list):
        return result
    return []


def fetch_stagehistory(filt: dict) -> list:
    """Полная выгрузка crm.stagehistory.list с пагинацией."""
    items: list[dict] = []
    start = 0
    while True:
        data = b24("crm.stagehistory.list", {
            "entityTypeId": 1,
            "order": {"OWNER_ID": "ASC", "ID": "ASC"},
            "filter": filt,
            "select": ["ID", "TYPE_ID", "OWNER_ID", "CREATED_TIME", "STATUS_ID"],
            "start": start,
        })
        batch = stagehistory_items(data)
        items.extend(batch)
        total = data.get("total")
        if not batch or (total is not None and len(items) >= total):
            break
        start += 50
    return items


# ── 1. События за сегодня → какие лиды двигались + id сегодняшних записей ──
today = datetime.now().date()
todays = fetch_stagehistory({
    ">=CREATED_TIME": f"{today}T00:00:00",
    "<=CREATED_TIME": f"{today}T23:59:59",
})
print(f"Записей истории за {today}: {len(todays)}")
if not todays:
    raise SystemExit(0)

owner_ids = list({str(e["OWNER_ID"]) for e in todays if e.get("OWNER_ID")})
today_record_ids = {str(e["ID"]) for e in todays}

# ── 2. Полная история этих лидов (чтобы знать "с какого статуса") ─────────
history: list[dict] = []
for i in range(0, len(owner_ids), 50):
    history.extend(fetch_stagehistory({"OWNER_ID": owner_ids[i:i + 50]}))

by_lead: dict[str, list] = {}
for h in history:
    by_lead.setdefault(str(h["OWNER_ID"]), []).append(h)
for lst in by_lead.values():
    lst.sort(key=lambda r: int(r["ID"]))

# ── 3. Справочники: статусы и операторы ─────────────────────────────────
st = b24("crm.status.list", {"filter": {"ENTITY_ID": "STATUS"}})
status_names = {str(r.get("STATUS_ID")): str(r.get("NAME") or r.get("STATUS_ID"))
                for r in (st.get("result") or [])}

assigned_by: dict[str, str] = {}
for i in range(0, len(owner_ids), 50):
    ld = b24("crm.lead.list", {"filter": {"ID": owner_ids[i:i + 50]},
                               "select": ["ID", "ASSIGNED_BY_ID"]})
    for r in (ld.get("result") or []):
        assigned_by[str(r.get("ID"))] = str(r.get("ASSIGNED_BY_ID") or "")

user_ids = list({v for v in assigned_by.values() if v})
user_names: dict[str, str] = {}
if user_ids:
    us = b24("user.get", {"FILTER": {"ID": user_ids}})
    for u in (us.get("result") or []):
        uid = str(u.get("ID"))
        user_names[uid] = " ".join(filter(None, [u.get("NAME"), u.get("LAST_NAME")])).strip() or f"#{uid}"


def sname(sid: str) -> str:
    return status_names.get(str(sid), str(sid))


# ── 4. Печать: для каждого сегодняшнего перехода берём предыдущий статус ──
print()
for lead_id, records in by_lead.items():
    op = user_names.get(assigned_by.get(lead_id, ""), "—")
    prev_status = None
    for rec in records:
        if str(rec["ID"]) in today_record_ids and str(rec.get("TYPE_ID")) != "1":
            from_status = sname(prev_status) if prev_status else "—"
            to_status = sname(rec.get("STATUS_ID"))
            print(
                f"Оператор: {op}  Лид: {lead_id}  "
                f"С какого статуса: {from_status},  "
                f"На какой статус: {to_status},  "
                f"Оператор: {op}"
            )
        prev_status = rec.get("STATUS_ID")
