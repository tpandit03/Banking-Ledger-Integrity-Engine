from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AccountType = Literal["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"]
Side = Literal["DEBIT", "CREDIT"]

class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    currency: str = Field(min_length=3, max_length=3)
    account_type: AccountType

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("currency must be a three-letter code")
        return value

class JournalLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str = Field(min_length=1, max_length=64)
    side: Side
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("amount must be finite and greater than zero")
        if value.as_tuple().exponent < -2:
            raise ValueError("amount supports at most two decimal places in this demo")
        return value

class JournalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=250)
    lines: list[JournalLineInput] = Field(min_length=2, max_length=100)

    @model_validator(mode="after")
    def require_balanced_lines(self):
        debit = sum((x.amount for x in self.lines if x.side == "DEBIT"), Decimal("0"))
        credit = sum((x.amount for x in self.lines if x.side == "CREDIT"), Decimal("0"))
        if debit != credit:
            raise ValueError("journal must balance: total debits must equal total credits")
        return self
