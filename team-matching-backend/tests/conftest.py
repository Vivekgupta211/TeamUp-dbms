import os
import uuid

import pymysql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.config import get_settings
from app.db import get_db
from app.main import app, settings
from scripts.init_db import initialize


@pytest.fixture
def client(monkeypatch):
    """Real MySQL only. Each test owns a fresh database with original triggers."""
    if not os.getenv("TEST_DB_HOST"):
        pytest.skip("Set TEST_DB_HOST, TEST_DB_PORT, TEST_DB_USER, TEST_DB_PASSWORD for MySQL integration tests")
    name = "team_matching_test_" + uuid.uuid4().hex
    for field, default in [("HOST", "127.0.0.1"), ("PORT", "3306"), ("USER", "root"), ("PASSWORD", "")]:
        monkeypatch.setenv("DB_" + field, os.getenv("TEST_DB_" + field, default))
    monkeypatch.setenv("DB_NAME", name)
    get_settings.cache_clear()
    config = get_settings()
    test_engine = create_engine(config.database_url, isolation_level="READ COMMITTED", pool_pre_ping=True)

    def override_db():
        with test_engine.begin() as db:
            yield db

    try:
        initialize()
        app.dependency_overrides[get_db] = override_db
        monkeypatch.setattr(settings, "api_key", "")
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()
        admin = pymysql.connect(
            host=config.db_host, port=config.db_port, user=config.db_user, password=config.db_password, autocommit=True
        )
        try:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{name}`")
        finally:
            admin.close()
            get_settings.cache_clear()
