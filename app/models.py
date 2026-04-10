from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict
from sqlmodel import Field, Relationship, SQLModel


class ParsedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float
    category: str
    raw: str
    confidence: float


class ParsedReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: float
    items: list[ParsedItem]
    confidence: float


class Receipt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    total: float
    items: list["Item"] = Relationship(back_populates="receipt")
    confidence: float
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(ZoneInfo("America/New_York"))
    )


class Item(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    receipt_id: int | None = Field(default=None, foreign_key="receipt.id")
    name: str
    price: float
    category: str
    raw: str
    confidence: float
    receipt: Receipt | None = Relationship(back_populates="items")


class Summary(BaseModel):
    total_spent: float
    receipt_count: int
    avg_receipt_total: float
    most_common_category: str


class TopItem(BaseModel):
    name: str
    total_spent: float
    times_purchased: int


class Stats(BaseModel):
    summary: Summary
    price_by_categories: dict[str, float]
    top_items: list[TopItem]
    spending_over_time: list[tuple[date, float]]
