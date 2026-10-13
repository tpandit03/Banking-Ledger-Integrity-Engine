from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from ledger.db import connect
from ledger.models import AccountCreate, JournalCreate

def to_minor(amount: Decimal) -> int:
    quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(quantized * 100)

def from_minor(amount_minor: int) -> str:
    return str((Decimal(amount_minor) / 100).quantize(Decimal("0.01")))

class LedgerError(Exception):
    pass

class ConflictError(LedgerError):
    pass

class NotFoundError(LedgerError):
    pass

def create_account(account: AccountCreate) -> dict:
    try:
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO accounts(account_id,name,currency,account_type) VALUES(?,?,?,?)",
                (account.account_id, account.name.strip(), account.currency, account.account_type),
            )
            row = conn.execute("SELECT * FROM accounts WHERE account_id=?", (account.account_id,)).fetchone()
            conn.commit()
            return dict(row)
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise ConflictError(f"account {account.account_id} already exists") from exc
        raise

def list_accounts() -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM accounts ORDER BY account_id").fetchall()]

def post_journal(journal: JournalCreate) -> dict:
    debit = sum(to_minor(x.amount) for x in journal.lines if x.side == "DEBIT")
    credit = sum(to_minor(x.amount) for x in journal.lines if x.side == "CREDIT")
    if debit != credit:
        raise LedgerError("journal must balance to the minor currency unit")

    currencies = set()
    try:
        with connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM journals WHERE idempotency_key=?", (journal.idempotency_key,)
            ).fetchone()
            request_fingerprint = (
                journal.description.strip(),
                tuple((x.account_id, x.side, to_minor(x.amount)) for x in journal.lines),
            )
            if existing:
                existing_lines = conn.execute(
                    "SELECT account_id, side, amount_minor FROM journal_lines WHERE journal_id=? ORDER BY line_number",
                    (existing["journal_id"],),
                ).fetchall()
                stored_fingerprint = (
                    existing["description"],
                    tuple((x["account_id"], x["side"], x["amount_minor"]) for x in existing_lines),
                )
                if request_fingerprint != stored_fingerprint:
                    raise ConflictError("idempotency key was already used with a different journal payload")
                result = _journal_detail(conn, existing["journal_id"])
                conn.commit()
                return result

            for line in journal.lines:
                account = conn.execute(
                    "SELECT account_id,currency FROM accounts WHERE account_id=?", (line.account_id,)
                ).fetchone()
                if not account:
                    raise NotFoundError(f"account {line.account_id} does not exist")
                currencies.add(account["currency"])
            if len(currencies) != 1:
                raise LedgerError("all journal lines must use accounts in the same currency")

            journal_id = str(uuid4())
            currency = next(iter(currencies))
            conn.execute(
                "INSERT INTO journals(journal_id,idempotency_key,description,currency,total_debit_minor,total_credit_minor) VALUES(?,?,?,?,?,?)",
                (journal_id, journal.idempotency_key, journal.description.strip(), currency, debit, credit),
            )
            conn.executemany(
                "INSERT INTO journal_lines(journal_id,line_number,account_id,side,amount_minor) VALUES(?,?,?,?,?)",
                [(journal_id, i, line.account_id, line.side, to_minor(line.amount))
                 for i, line in enumerate(journal.lines, start=1)],
            )
            result = _journal_detail(conn, journal_id)
            conn.commit()
            return result
    except (ConflictError, NotFoundError, LedgerError):
        raise
    except Exception as exc:
        if "UNIQUE constraint failed: journals.idempotency_key" in str(exc):
            raise ConflictError("idempotency key already exists") from exc
        raise

def _journal_detail(conn, journal_id: str) -> dict:
    journal = conn.execute("SELECT * FROM journals WHERE journal_id=?", (journal_id,)).fetchone()
    if not journal:
        raise NotFoundError(f"journal {journal_id} not found")
    lines = conn.execute(
        "SELECT line_number,account_id,side,amount_minor FROM journal_lines WHERE journal_id=? ORDER BY line_number",
        (journal_id,),
    ).fetchall()
    result = dict(journal)
    result["total_debit"] = from_minor(result.pop("total_debit_minor"))
    result["total_credit"] = from_minor(result.pop("total_credit_minor"))
    result["lines"] = [
        {"line_number": x["line_number"], "account_id": x["account_id"], "side": x["side"],
         "amount": from_minor(x["amount_minor"])} for x in lines
    ]
    return result

def get_journal(journal_id: str) -> dict:
    with connect() as conn:
        return _journal_detail(conn, journal_id)

def account_balance(account_id: str) -> dict:
    with connect() as conn:
        account = conn.execute("SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone()
        if not account:
            raise NotFoundError(f"account {account_id} not found")
        totals = conn.execute(
            "SELECT side, COALESCE(SUM(amount_minor),0) AS total FROM journal_lines WHERE account_id=? GROUP BY side",
            (account_id,),
        ).fetchall()
        debit = sum(r["total"] for r in totals if r["side"] == "DEBIT")
        credit = sum(r["total"] for r in totals if r["side"] == "CREDIT")
        debit_normal = account["account_type"] in ("ASSET", "EXPENSE")
        signed = debit - credit if debit_normal else credit - debit
        return {
            "account_id": account_id,
            "name": account["name"],
            "currency": account["currency"],
            "account_type": account["account_type"],
            "balance": from_minor(signed),
            "balance_convention": "debit-positive" if debit_normal else "credit-positive",
        }

def integrity_check() -> dict:
    problems = []
    with connect() as conn:
        journals = conn.execute("SELECT * FROM journals ORDER BY created_at").fetchall()
        for journal in journals:
            lines = conn.execute(
                "SELECT side, amount_minor FROM journal_lines WHERE journal_id=?",
                (journal["journal_id"],),
            ).fetchall()
            debits = sum(x["amount_minor"] for x in lines if x["side"] == "DEBIT")
            credits = sum(x["amount_minor"] for x in lines if x["side"] == "CREDIT")
            if debits != credits:
                problems.append({"journal_id": journal["journal_id"], "problem": "line totals are not balanced"})
            if debits != journal["total_debit_minor"] or credits != journal["total_credit_minor"]:
                problems.append({"journal_id": journal["journal_id"], "problem": "stored header totals differ from line totals"})
            if len(lines) < 2:
                problems.append({"journal_id": journal["journal_id"], "problem": "journal has fewer than two lines"})
        return {"ok": not problems, "journals_checked": len(journals), "problems": problems}
