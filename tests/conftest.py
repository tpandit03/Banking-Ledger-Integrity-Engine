import os
import pytest

@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_DB_PATH", str(tmp_path / "test-ledger.db"))
    # Import after env setup so each test initializes its own isolated database.
    from ledger.db import init_db
    init_db()
