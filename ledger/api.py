from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from ledger.db import init_db
from ledger.models import AccountCreate, JournalCreate
from ledger.service import (
    ConflictError, LedgerError, NotFoundError, account_balance,
    create_account, get_journal, integrity_check, list_accounts, post_journal,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Banking Ledger Integrity Engine",
    version="0.1.0",
    description="Educational double-entry ledger API with idempotent posting and integrity checks.",
    lifespan=lifespan,
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/accounts", status_code=201)
def add_account(account: AccountCreate):
    try:
        return create_account(account)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@app.get("/accounts")
def accounts():
    return list_accounts()

@app.get("/accounts/{account_id}/balance")
def balance(account_id: str):
    try:
        return account_balance(account_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.post("/journals", status_code=201)
def create_journal(journal: JournalCreate):
    try:
        return post_journal(journal)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LedgerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.get("/journals/{journal_id}")
def journal_detail(journal_id: str):
    try:
        return get_journal(journal_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.get("/integrity/check")
def check_integrity():
    return integrity_check()
