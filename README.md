# Banking Ledger Integrity Engine

A runnable educational reference implementation of a double-entry ledger API. It demonstrates balanced journal posting, idempotency keys, atomic persistence, immutable posted entries, and integrity verification.

> **Safety notice:** This project is for learning and portfolio demonstration only. It is not a certified banking core or production accounting system. Use synthetic data only. Production use requires independent security, accounting, legal/compliance, resilience, and operational review.

## What it demonstrates

- Double-entry journal entries: debits must equal credits per currency
- Decimal arithmetic for money
- SQLite persistence with transactional posting
- Idempotent posting via a caller-provided idempotency key
- Prevents updates/deletes to posted journal lines through the application interface
- Account and currency validation
- Ledger integrity verification
- REST API with FastAPI and interactive Swagger docs
- Unit and API tests plus GitHub Actions CI

## Requirements

Python 3.11 or newer.

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"
pytest -v
uvicorn ledger.api:app --reload
```

Open `http://127.0.0.1:8000/docs`.

The database defaults to `ledger.db` in the current working directory. Set `LEDGER_DB_PATH` to choose another path.

## Quick API walkthrough

### 1. Create accounts

Use `POST /accounts`:

```json
{
  "account_id": "CASH-USD",
  "name": "Cash",
  "currency": "USD",
  "account_type": "ASSET"
}
```

Create a second account, for example `CUSTOMER-USD`, with type `LIABILITY`.

### 2. Post a balanced journal

Use `POST /journals`:

```json
{
  "idempotency_key": "demo-deposit-001",
  "description": "Synthetic customer deposit",
  "lines": [
    {"account_id": "CASH-USD", "side": "DEBIT", "amount": "100.00"},
    {"account_id": "CUSTOMER-USD", "side": "CREDIT", "amount": "100.00"}
  ]
}
```

Repeat the exact request with the same idempotency key to get the existing journal back rather than posting twice.

### 3. Verify integrity

- `GET /journals/{journal_id}` retrieves a posted journal.
- `GET /accounts/{account_id}/balance` returns the account balance using debit-positive accounting convention for assets/expenses and credit-positive convention for liabilities/equity/revenue.
- `GET /integrity/check` verifies stored journals are balanced and that stored line totals agree with the journal totals.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Service health |
| `POST` | `/accounts` | Create an account |
| `GET` | `/accounts` | List accounts |
| `GET` | `/accounts/{account_id}/balance` | Calculate account balance |
| `POST` | `/journals` | Atomically post a balanced journal |
| `GET` | `/journals/{journal_id}` | Retrieve journal details |
| `GET` | `/integrity/check` | Run integrity checks |

## Design decisions and limitations

- Amounts are represented with `Decimal` at the API boundary and stored as integer minor units in SQLite to avoid floating-point arithmetic.
- A journal is committed as one SQLite transaction. A failure rolls back the complete journal.
- An idempotency key prevents a repeated request from creating a second journal. Reusing a key with a different request is rejected.
- Each journal must use one currency and at least two lines; total debits must equal total credits.
- Posted journals are not edited. Corrections should be represented by a new compensating journal, which is not automated in this starter.
- This sample uses simplified account-balance conventions and currency precision (two decimal places). Real systems need currency-specific minor units, accounting policy, access controls, audit retention, database migrations, observability, backups, disaster recovery, and security hardening.
