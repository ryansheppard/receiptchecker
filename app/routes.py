import hashlib
from datetime import date

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.anthropic import parse_receipt, redis_client
from app.database import engine
from app.models import Item, ParsedItem, ParsedReceipt, Receipt, Stats, Summary, TopItem

router = APIRouter()


@router.post("/receipt")
async def handle_receipt(file: UploadFile) -> ParsedReceipt:
    data = await file.read()
    digest = hashlib.sha256(data).hexdigest()
    value = await redis_client.get(digest)
    if value:
        return ParsedReceipt.model_validate_json(value)

    parsed = await parse_receipt(data, file.content_type or "image/jpeg")
    await redis_client.set(digest, parsed.model_dump_json(), 3600)
    return parsed


class SubmitRequest(BaseModel):
    total: float
    confidence: float
    items: list[ParsedItem]


@router.post("/submit")
async def handle_submit(body: SubmitRequest) -> Receipt:
    receipt = Receipt(total=body.total, confidence=body.confidence)
    receipt.items = [Item(**item.model_dump()) for item in body.items]
    with Session(engine) as session:
        session.add(receipt)
        session.commit()
        session.refresh(receipt)
    return receipt


@router.get("/stats")
async def stats() -> Stats:
    with Session(engine) as session:
        statement = select(Receipt)
        receipts = session.exec(statement).all()

        total_cost = sum([r.total for r in receipts])
        receipt_count = len(receipts)
        avg_cost = total_cost / receipt_count if receipt_count else 0.0

        price_by_categories = session.exec(
            select(Item.category, func.sum(Item.price))
            .where(Item.price > 0)
            .where(Item.category != "tax")
            .group_by(Item.category)
        ).all()

        top_items = session.exec(
            select(Item.name, func.sum(Item.price), func.count())
            .where(Item.price > 0)
            .where(Item.category != "tax")
            .group_by(Item.name)
            .order_by(func.sum(Item.price).desc())
            .limit(10)
        ).all()

        top_category = session.exec(
            select(Item.category, func.count())
            .group_by(Item.category)
            .order_by(func.count().desc())
            .limit(1)
        ).first()

        finalized_items: list[TopItem] = []
        for item in top_items:
            finalized_items.append(
                TopItem(name=item[0], total_spent=item[1], times_purchased=item[2])
            )

        spending_over_time = session.exec(
            select(func.date(Receipt.submitted_at), func.sum(Receipt.total))
            .group_by(func.date(Receipt.submitted_at))
            .order_by(func.date(Receipt.submitted_at))
        ).all()

        return Stats(
            summary=Summary(
                total_spent=total_cost,
                receipt_count=receipt_count,
                avg_receipt_total=avg_cost,
                most_common_category=top_category[0]
                if top_category
                else "No top category",
            ),
            price_by_categories=dict(price_by_categories),
            top_items=finalized_items,
            spending_over_time=[
                (date.fromisoformat(row[0]), row[1]) for row in spending_over_time
            ],
        )
