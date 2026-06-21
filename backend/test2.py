import httpx
import time

# Токен вашего вебхука
BASE_URL = "https://bitrix.raafgroup.kz/rest/40/1jqehhzagbzna61w"
CRM_URL = f"{BASE_URL}/crm.activity.list.json"


def get_absolutely_all_chats():
    start = 0
    all_chats = []
    page_counter = 1

    print("=== ЗАПУСК ПОЛНОЙ ВЫГРУЗКИ ВСЕЙ ИСТОРИИ ЧАТОВ ===")
    print("Внимание: процесс может занять время, если у вас много данных.\n")

    while True:
        crm_payload = {
            "filter": {
                # Ищем Wazzup и встроенные Открытые линии
                "PROVIDER_ID": ["WAZZUP", "IMOPENLINES"]
                # Фильтры по датам убраны — Битрикс начнет отдавать данные с самых старых (или новых)
            },
            "select": [
                "ID",
                "SUBJECT",
                "START_TIME",
                "DESCRIPTION",
                "RESPONSIBLE_ID",
                "OWNER_TYPE_ID",
                "OWNER_ID"
            ],
            "start": start
        }

        try:
            response = httpx.post(CRM_URL, json=crm_payload)
            response.raise_for_status()

            data = response.json()
            batch = data.get("result", [])

            if not batch:
                print("Данные закончились.")
                break

            all_chats.extend(batch)
            print(f"Страница {page_counter}: загружено {len(batch)} шт. (Всего собрано: {len(all_chats)})")

            # Проверяем, есть ли ещё данные дальше
            if "next" in data:
                start = data["next"]
                page_counter += 1
                # Обязательная пауза 0.4 секунды. Без нее Битрикс заблокирует вебхук за спам-запросы
                time.sleep(0.4)
            else:
                break

        except httpx.HTTPStatusError as e:
            print(f"\n❌ Ошибка API на странице {page_counter}: {e.response.status_code} - {e.response.text}")
            break
        except Exception as e:
            print(f"\n❌ Непредвиденная ошибка в коде: {e}")
            break

    print(f"\n Найдено и скачано чатов за ВСЮ историю: {len(all_chats)}\n")
    return all_chats


# Запускаем сбор данных
total_history = get_absolutely_all_chats()

# Пример обработки: выведем первые 10 чатов для проверки структуры
print("=== Пример первых 10 записей из истории ===")
for chat in total_history[:10]:
    print(f"Дело ID: {chat.get('ID')} | Оператор ID: {chat.get('RESPONSIBLE_ID')} | Дата: {chat.get('START_TIME')}")
    print(f"Тема: {chat.get('SUBJECT')}")
    print(f"Содержимое: {chat.get('DESCRIPTION', '(Пусто)')[:150]}...")  # Показываем первые 150 символов текста
    print("-" * 50)