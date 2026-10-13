import os
import sqlite3
from pathlib import Path

def db_path() -> str:
    return os.environ.get("LEDGER_DB_PATH", "ledger.db")

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db() -> None:
    Path(db_path()).parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            currency TEXT NOT NULL CHECK(length(currency) = 3),
            account_type TEXT NOT NULL CHECK(account_type IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')),
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );

        CREATE TABLE IF NOT EXISTS journals (
            journal_id TEXT PRIMARY KEY,
            idempotency_key TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            currency TEXT NOT NULL,
            total_debit_minor INTEGER NOT NULL,
            total_credit_minor INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            CHECK(total_debit_minor = total_credit_minor)
        );

        CREATE TABLE IF NOT EXISTS journal_lines (
            line_id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_id TEXT NOT NULL REFERENCES journals(journal_id),
            line_number INTEGER NOT NULL,
            account_id TEXT NOT NULL REFERENCES accounts(account_id),
            side TEXT NOT NULL CHECK(side IN ('DEBIT','CREDIT')),
            amount_minor INTEGER NOT NULL CHECK(amount_minor > 0),
            UNIQUE(journal_id, line_number)
        );

        CREATE INDEX IF NOT EXISTS idx_journal_lines_account ON journal_lines(account_id);
        CREATE INDEX IF NOT EXISTS idx_journal_lines_journal ON journal_lines(journal_id);
        """)
