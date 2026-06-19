"""Seed an admin account.

Usage:
    pipenv run python seed_admin.py
    # or override:
    ADMIN_LOGIN=root ADMIN_PASSWORD=secret pipenv run python seed_admin.py
"""
import asyncio
import os
import sys

from app.auth import hash_password
from app.database import ensure_indexes, users

ADMIN_LOGIN = os.environ.get("ADMIN_LOGIN", "admin").lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "adminpass")
ADMIN_NAME = os.environ.get("ADMIN_NAME", "Administrator")


async def main() -> int:
    await ensure_indexes()

    existing = await users.find_one({"login": ADMIN_LOGIN})
    if existing:
        print(f"[seed_admin] user '{ADMIN_LOGIN}' already exists — nothing to do")
        return 0

    await users.insert_one({
        "login": ADMIN_LOGIN,
        "name": ADMIN_NAME,
        "password_hash": hash_password(ADMIN_PASSWORD),
    })
    print(f"[seed_admin] created user '{ADMIN_LOGIN}' (password: '{ADMIN_PASSWORD}')")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
