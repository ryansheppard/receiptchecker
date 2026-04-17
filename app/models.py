from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ParsedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float
    category: str
    raw: str
    confidence: float

    @field_validator("category", "name")
    @classmethod
    def lowercase_category(cls, v: str) -> str:
        return v.lower()


class ParsedReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: float
    items: list[ParsedItem]
    confidence: float


class Receipt(Base):
    __tablename__ = "receipt"

    id: Mapped[int] = mapped_column(primary_key=True)
    total: Mapped[float]
    confidence: Mapped[float]
    submitted_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(ZoneInfo("America/New_York"))
    )
    items: Mapped[list["Item"]] = relationship(back_populates="receipt")


class Item(Base):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int | None] = mapped_column(
        ForeignKey("receipt.id"), default=None
    )
    name: Mapped[str]
    price: Mapped[float]
    category: Mapped[str]
    raw: Mapped[str]
    confidence: Mapped[float]
    receipt: Mapped["Receipt | None"] = relationship(back_populates="items")


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


class ItemStat(BaseModel):
    name: str
    count: int
    total_spent: float


class RenameRequest(BaseModel):
    old_name: str
    new_name: str


class SubmitRequest(BaseModel):
    total: float
    confidence: float
    items: list[ParsedItem]


class ReceiptItem(BaseModel):
    id: int
    name: str
    price: float
    category: str


class UpdateItemRequest(BaseModel):
    name: str
    price: float
    category: str

    @field_validator("category", "name")
    @classmethod
    def lowercase_category(cls, v: str) -> str:
        return v.lower()


class ReceiptWithItems(BaseModel):
    id: int
    submitted_at: datetime
    total: float
    confidence: float
    items: list[ReceiptItem]


class ReceiptOut(BaseModel):
    id: int
    total: float
    confidence: float
    submitted_at: datetime
