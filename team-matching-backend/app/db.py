from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from app.config import get_settings

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    isolation_level="READ COMMITTED",
    connect_args={"connect_timeout": 5},
)


def get_db():
    # Commit/rollback the entire HTTP operation, including trigger side effects.
    with engine.begin() as connection:
        yield connection


DB = Annotated[Connection, Depends(get_db, scope="function")]


def rows(db, sql, **params):
    return [{k.lower(): v for k, v in row.items()} for row in db.execute(text(sql), params).mappings()]


def run(db, sql, **params):
    return db.execute(text(sql), params)


def one(db, table, key, value, *, lock=False):
    # All identifiers are application constants, never request input.
    found = rows(db, f"SELECT * FROM {table} WHERE {key} = :id" + (" FOR UPDATE" if lock else ""), id=value)
    if not found:
        raise HTTPException(404, f"{table.title()} not found")
    return found[0]


def update(db, table, key, value, data):
    if data:
        assignments = ", ".join(f"{column} = :{column}" for column in data)
        run(db, f"UPDATE {table} SET {assignments} WHERE {key} = :_id", _id=value, **data)


def insert(db, table, data):
    columns = ", ".join(data)
    values = ", ".join(f":{column}" for column in data)
    return run(db, f"INSERT INTO {table} ({columns}) VALUES ({values})", **data).lastrowid


def conflict(message):
    raise HTTPException(409, message)
