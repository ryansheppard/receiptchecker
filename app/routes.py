import hashlib
from datetime import date

import redis.asyncio as redis
from fastapi import APIRouter, HTTPException, UploadFile
from rapidfuzz import fuzz
from sqlmodel import Session, func, select

from app.anthropic import parse_receipt
from app.database import engine
from app.models import (
    Item,
    ItemStat,
    ParsedReceipt,
    Receipt,
    RenameRequest,
    Stats,
    SubmitRequest,
    Summary,
    TopItem,
)

router = APIRouter()

redis_client = redis.Redis()


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


@router.get("/api/items")
async def items() -> list[ItemStat]:
    with Session(engine) as session:
        rows = session.exec(
            select(Item.name, func.count(), func.sum(Item.price))
            .group_by(Item.name)
            .order_by(Item.name)
        ).all()

        return [
            ItemStat(name=r[0], count=r[1], total_spent=round(r[2], 2)) for r in rows
        ]


@router.patch("/api/items/rename")
async def rename_items(body: RenameRequest) -> dict[str, int]:
    new_name = body.new_name.strip()
    if not new_name:
        raise HTTPException(status_code=422, detail="new_name must not be empty")
    with Session(engine) as session:
        items = session.exec(select(Item).where(Item.name == body.old_name)).all()
        for item in items:
            item.name = new_name
            session.add(item)
        session.commit()
    return {"updated": len(items)}


@router.get("/api/items/similar")
async def similar_items(threshold: float = 80) -> list[list[str]]:
    with Session(engine) as session:
        names = session.exec(select(Item.name).distinct().order_by(Item.name)).all()

    n = len(names)
    adj: dict[int, set[int]] = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if fuzz.token_set_ratio(names[i], names[j]) >= threshold:
                adj[i].add(j)
                adj[j].add(i)

    visited: set[int] = set()
    clusters: list[list[str]] = []
    for start in range(n):
        if start in visited or not adj[start]:
            continue
        queue = [start]
        component: list[str] = []
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(names[node])
            queue.extend(adj[node] - visited)
        if len(component) > 1:
            clusters.append(sorted(component))

    return clusters
