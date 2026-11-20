from datetime import date as DateType
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExpenseCreateRequest(BaseModel):
    """Fields a client may send to create an expense."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category: str = Field(min_length=1, max_length=50)
    expense_date: DateType


class ExpenseUpdateRequest(BaseModel):
    """Partial update; only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    expense_date: DateType | None = None


class ExpenseResponse(BaseModel):
    """An expense as returned to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    amount: Decimal
    category: str
    expense_date: DateType
    created_at: datetime
    updated_at: datetime


class ExpenseListParams(BaseModel):
    """Query parameters for listing expenses."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    search: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=50)
    start_date: DateType | None = None
    end_date: DateType | None = None

    @model_validator(mode="after")
    def check_date_range(self) -> "ExpenseListParams":
        """Reject a range whose start is after its end."""
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date.")
        return self


class ExpenseListResponse(BaseModel):
    """One page of expenses."""

    items: list[ExpenseResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
