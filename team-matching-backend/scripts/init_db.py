"""Import supplied schema + fixtures into an EMPTY database; never drop a database."""

import re
from pathlib import Path

import pymysql

from app.config import get_settings


def statements(source):
    delimiter, buffer = ";", []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER "):
            delimiter = stripped.split()[1]
            continue
        if not stripped or stripped.startswith("--"):
            continue
        # The supplied script uses end-of-line -- comments outside string literals.
        line = re.sub(r"\s+--\s.*$", "", line)
        buffer.append(line)
        if line.rstrip().endswith(delimiter):
            yield "\n".join(buffer).rstrip()[: -len(delimiter)].strip()
            buffer = []
    if buffer:
        raise ValueError("Incomplete SQL statement")


def initialize():
    settings = get_settings()
    if not re.fullmatch(r"[a-zA-Z0-9_]+", settings.db_name):
        raise ValueError("DB_NAME must contain only letters, numbers, and underscores")
    connection = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{settings.db_name}` CHARACTER SET utf8mb4")
            connection.select_db(settings.db_name)
            cursor.execute("SHOW FULL TABLES")
            if cursor.fetchall():
                raise SystemExit(
                    "Database is not empty. Nothing was overwritten. Use the existing database or choose a new DB_NAME."
                )
            source = (Path(__file__).resolve().parents[1] / "database" / "original.sql").read_text()
            for statement in statements(source):
                if re.match(r"^(DROP DATABASE|CREATE DATABASE|USE\s)", statement, re.I):
                    continue
                cursor.execute(statement)
        print(f"Initialized {settings.db_name} with original tables, triggers, views, and sample data.")
    finally:
        connection.close()


if __name__ == "__main__":
    initialize()
