"""Создаёт (или повышает до админа) пользователя ownAi.

Использование:
    # из переменных окружения
    ADMIN_LOGIN=root ADMIN_PASSWORD=secret ADMIN_NAME="Главный" \\
        pipenv run python seed_admin.py

    # из аргументов
    pipenv run python seed_admin.py admin "Admin" pwd123

    # интерактивно
    pipenv run python seed_admin.py
"""
import asyncio
import getpass
import os
import re
import sys

LOGIN_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


async def main() -> int:
    # импорт внутри async-функции, чтобы motor привязался к свежему loop
    from app.auth import hash_password
    from app.database import ensure_indexes, users

    await ensure_indexes()

    args = sys.argv[1:]

    login = (args[0] if len(args) > 0 else os.environ.get("ADMIN_LOGIN", "")).strip().lower()
    name = (args[1] if len(args) > 1 else os.environ.get("ADMIN_NAME", "")).strip()
    password = args[2] if len(args) > 2 else os.environ.get("ADMIN_PASSWORD", "")

    if not login:
        login = input("Логин: ").strip().lower()
    if not name:
        name = input("Имя (Enter = логин): ").strip() or login
    if not password:
        password = getpass.getpass("Пароль: ")
        if getpass.getpass("Пароль ещё раз: ") != password:
            print("Пароли не совпадают", file=sys.stderr)
            return 1

    if not LOGIN_RE.match(login):
        print(
            "Логин должен быть 3–32 символа: латиница, цифры, точка, тире, подчёркивание",
            file=sys.stderr,
        )
        return 1
    if len(password) < 6:
        print("Пароль минимум 6 символов", file=sys.stderr)
        return 1

    password_hash = hash_password(password)
    existing = await users.find_one({"login": login})

    if existing:
        await users.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "name": name,
                    "password_hash": password_hash,
                    "is_admin": True,
                }
            },
        )
        print(f"✓ @{login} обновлён и назначен админом (id={existing['_id']})")
        return 0

    doc = {
        "login": login,
        "name": name,
        "password_hash": password_hash,
        "phone": "",
        "email": "",
        "address": "",
        "is_admin": True,
    }
    result = await users.insert_one(doc)
    print(f"✓ Создан админ @{login} (id={result.inserted_id})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
