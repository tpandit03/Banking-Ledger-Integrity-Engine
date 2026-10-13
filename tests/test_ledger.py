from fastapi.testclient import TestClient
from ledger.api import app
from ledger.db import init_db
from ledger.models import AccountCreate, JournalCreate
from ledger.service import ConflictError, LedgerError, create_account, integrity_check, post_journal

client = TestClient(app)

def make_accounts():
    init_db()
    client.post("/accounts", json={"account_id":"CASH-USD","name":"Cash","currency":"USD","account_type":"ASSET"})
    client.post("/accounts", json={"account_id":"CUSTOMER-USD","name":"Customer deposits","currency":"USD","account_type":"LIABILITY"})

def balanced_payload(key="deposit-1"):
    return {
      "idempotency_key": key,
      "description": "Synthetic customer deposit",
      "lines": [
        {"account_id":"CASH-USD","side":"DEBIT","amount":"100.00"},
        {"account_id":"CUSTOMER-USD","side":"CREDIT","amount":"100.00"}
      ]
    }

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_unbalanced_journal_rejected():
    make_accounts()
    payload = balanced_payload()
    payload["lines"][1]["amount"] = "99.00"
    response = client.post("/journals", json=payload)
    assert response.status_code == 422

def test_post_balanced_journal_and_integrity():
    make_accounts()
    response = client.post("/journals", json=balanced_payload())
    assert response.status_code == 201
    journal = response.json()
    assert journal["total_debit"] == "100.00"
    assert journal["total_credit"] == "100.00"
    assert client.get("/integrity/check").json()["ok"] is True

def test_idempotency_returns_same_journal():
    make_accounts()
    first = client.post("/journals", json=balanced_payload())
    second = client.post("/journals", json=balanced_payload())
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["journal_id"] == second.json()["journal_id"]

def test_reusing_key_with_different_payload_rejected():
    make_accounts()
    client.post("/journals", json=balanced_payload())
    changed = balanced_payload()
    changed["lines"][0]["amount"] = "101.00"
    changed["lines"][1]["amount"] = "101.00"
    response = client.post("/journals", json=changed)
    assert response.status_code == 409

def test_unknown_account_rejected_without_partial_post():
    make_accounts()
    payload = balanced_payload()
    payload["lines"][1]["account_id"] = "MISSING"
    response = client.post("/journals", json=payload)
    assert response.status_code == 404
    assert client.get("/integrity/check").json()["journals_checked"] == 0

def test_account_balances():
    make_accounts()
    client.post("/journals", json=balanced_payload())
    cash = client.get("/accounts/CASH-USD/balance").json()
    liability = client.get("/accounts/CUSTOMER-USD/balance").json()
    assert cash["balance"] == "100.00"
    assert liability["balance"] == "100.00"

def test_account_currency_mismatch_rejected():
    make_accounts()
    client.post("/accounts", json={"account_id":"CUSTOMER-EUR","name":"Euro deposits","currency":"EUR","account_type":"LIABILITY"})
    payload = {
      "idempotency_key":"cross-currency",
      "description":"Should not post",
      "lines":[
        {"account_id":"CASH-USD","side":"DEBIT","amount":"10.00"},
        {"account_id":"CUSTOMER-EUR","side":"CREDIT","amount":"10.00"}
      ]
    }
    response = client.post("/journals", json=payload)
    assert response.status_code == 422
