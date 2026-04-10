from datetime import datetime, timezone

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
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Item(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    receipt_id: int | None = Field(default=None, foreign_key="receipt.id")
    name: str
    price: float
    category: str
    raw: str
    confidence: float
    receipt: Receipt | None = Relationship(back_populates="items")
