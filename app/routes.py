import hashlib

import redis.asyncio as redis
from fastapi import APIRouter, HTTPException, UploadFile
from rapidfuzz import fuzz
from sqlmodel import Session

from app.anthropic import parse_receipt
from app.database import (
    engine,
    get_all_items,
    get_distinct_item_names,
    get_price_by_categories,
    get_receipt_summary,
    get_receipts_with_items,
    get_spending_over_time,
    get_top_items,
    rename_items_by_name,
    save_receipt,
    update_item,
)
from app.models import (
    Item,
    ItemStat,
    ParsedReceipt,
    Receipt,
    ReceiptItem,
    ReceiptWithItems,
    RenameRequest,
    Stats,
    SubmitRequest,
    UpdateItemRequest,
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
        return save_receipt(session, receipt)


@router.get("/stats")
async def stats() -> Stats:
    with Session(engine) as session:
        return Stats(
            summary=get_receipt_summary(session),
            price_by_categories=get_price_by_categories(session),
            top_items=get_top_items(session),
            spending_over_time=get_spending_over_time(session),
        )


@router.get("/api/items")
async def items() -> list[ItemStat]:
    with Session(engine) as session:
        return get_all_items(session)


@router.patch("/api/items/rename")
async def rename_items(body: RenameRequest) -> dict[str, int]:
    new_name = body.new_name.strip()
    if not new_name:
        raise HTTPException(status_code=422, detail="new_name must not be empty")
    with Session(engine) as session:
        return {"updated": rename_items_by_name(session, body.old_name, new_name)}


@router.get("/api/items/similar")
async def similar_items(threshold: float = 80) -> list[list[str]]:
    with Session(engine) as session:
        names = get_distinct_item_names(session)

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


@router.get("/api/receipts")
async def get_receipts() -> list[ReceiptWithItems]:
    with Session(engine) as session:
        receipts = get_receipts_with_items(session)

    return receipts


@router.patch("/api/receipts/{receipt_id}/items/{item_id}")
async def update_receipt_item(
    receipt_id: int, item_id: int, body: UpdateItemRequest
) -> ReceiptItem:
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="name must not be empty")
    with Session(engine) as session:
        item = update_item(session, receipt_id, item_id, body)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return ReceiptItem(
        id=item.id or 0, name=item.name, price=item.price, category=item.category
    )
