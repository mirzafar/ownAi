"""Cron-скрипт: синхронизация истории смены статусов лидов из Bitrix в БД.

Наполняет коллекцию `lead_status_events`, из которой считается аналитика
по операторам на экране /operators/:id.

Использование:
    # синк за сегодня (по умолчанию)
    pipenv run python sync_lead_status.py

    # синк за последние N дней (включая сегодня) — с запасом на пропуски
    pipenv run python sync_lead_status.py 3

    # синк за явный период
    pipenv run python sync_lead_status.py 2026-08-01 2026-08-19

Пример crontab (каждый день в 00:30, с перекрытием на 2 дня):
    30 0 * * * cd /path/to/backend && pipenv run python sync_lead_status.py 2 >> /var/log/lead_sync.log 2>&1
"""
import asyncio
import sys
from datetime import date, timedelta


async def main() -> int:
    # импорт внутри корутины — чтобы motor привязался к текущему event loop
    from app.services.lead_status_sync import sync_range

    args = sys.argv[1:]

    if len(args) == 2:
        # явный период: YYYY-MM-DD YYYY-MM-DD
        date_from, date_to = args[0], args[1]
    else:
        # N дней назад включая сегодня (по умолчанию 1 = только сегодня)
        days = int(args[0]) if len(args) == 1 else 1
        today = date.today()
        date_from = (today - timedelta(days=days - 1)).isoformat()
        date_to = today.isoformat()

    stats = await sync_range(date_from, date_to)
    print(f"✓ Синк {date_from}..{date_to}: "
          f"получено {stats['fetched']} записей, "
          f"записано {stats['written']}, лидов {stats['leads']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
