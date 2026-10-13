# Architecture

```text
Client
  |
  v
FastAPI + Pydantic validation
  |
  v
Ledger service
  |-- account and currency validation
  |-- idempotency check
  |-- debit/credit balance check
  |-- atomic SQLite transaction
  |
  v
SQLite: accounts / journals / journal_lines
  |
  v
Balance queries + integrity checker
```

## Invariants

1. Every journal has at least two lines.
2. Debits equal credits in minor units.
3. Every line references an existing account.
4. All lines in one journal use the same currency.
5. Idempotency keys are unique; a key cannot be reused with a different payload.
6. Journal posting is atomic: all rows commit together or none do.

## Limitations

The sample is a single-currency-per-journal demo with two decimal places. It has no authentication, authorization, tenant isolation, maker-checker approval, production audit retention, migration framework, or multi-region recovery. SQLite is suitable for a local demonstration, not a high-throughput core banking deployment.
