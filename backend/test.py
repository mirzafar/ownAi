import httpx

# Базовый URL вашего вебхука + метод для получения статистики звонков
URL = "https://bitrix.raafgroup.kz/rest/40/1jqehhzagbzna61w/voximplant.statistic.get.json"

# Параметры запроса (например, выгрузим звонки за июнь 2026 года)
payload = {
    "FILTER": {
        ">=CALL_START_DATE": "2026-06-01T00:00:00",
        "<=CALL_START_DATE": "2026-06-30T23:59:59"
    },
    "SORT": "ID",
    "ORDER": "DESC",  # Сначала новые
    "start": 0  # Смещение (для пагинации)
}

response = httpx.post(URL, json=payload)
response.raise_for_status()  # Проверяем на ошибки HTTP

data = response.json()

# Список звонков лежит в ключе 'result'
calls = data.get("result", [])
print(f"Успешно получено звонков: {len(calls)}")

for call in calls:
    print()
    print(call)
