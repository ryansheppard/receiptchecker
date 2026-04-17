from datetime import date

from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, create_engine, func, select

from app.models import (
    Item,
    ItemStat,
    Receipt,
    ReceiptItem,
    ReceiptWithItems,
    Summary,
    TopItem,
    UpdateItemRequest,
)

engine = create_engine("sqlite:///sqlite.db")


def get_receipt_summary(session: Session) -> Summary:
    total_cost = session.exec(select(func.sum(Receipt.total))).first()
    receipt_count = session.exec(select(func.count()).select_from(Receipt)).first()
    avg_cost = session.exec(select(func.avg(Receipt.total))).first()
    top_category = session.exec(
        select(Item.category, func.count())
        .group_by(Item.category)
        .order_by(func.count().desc())
        .limit(1)
    ).first()
    return Summary(
        total_spent=total_cost if total_cost else 0.0,
        receipt_count=receipt_count if receipt_count else 0,
        avg_receipt_total=avg_cost if avg_cost else 0.0,
        most_common_category=top_category[0] if top_category else "No top category",
    )


def get_price_by_categories(session: Session) -> dict[str, float]:
    rows = session.exec(
        select(Item.category, func.sum(Item.price))
        .where(Item.price > 0)
        .where(Item.category != "tax")
        .group_by(Item.category)
    ).all()
    return dict(rows)


def get_top_items(session: Session) -> list[TopItem]:
    rows = session.exec(
        select(Item.name, func.sum(Item.price), func.count())
        .where(Item.price > 0)
        .where(Item.category != "tax")
        .group_by(Item.name)
        .order_by(func.sum(Item.price).desc())
        .limit(10)
    ).all()
    return [TopItem(name=r[0], total_spent=r[1], times_purchased=r[2]) for r in rows]


def get_spending_over_time(session: Session) -> list[tuple[date, float]]:
    rows = session.exec(
        select(func.date(Receipt.submitted_at), func.sum(Receipt.total))
        .group_by(func.date(Receipt.submitted_at))
        .order_by(func.date(Receipt.submitted_at))
    ).all()
    return [(date.fromisoformat(row[0]), row[1]) for row in rows]


def save_receipt(session: Session, receipt: Receipt) -> Receipt:
    session.add(receipt)
    session.commit()
    session.refresh(receipt)
    return receipt


def get_all_items(session: Session) -> list[ItemStat]:
    rows = session.exec(
        select(Item.name, func.count(), func.sum(Item.price))
        .group_by(Item.name)
        .order_by(Item.name)
    ).all()
    return [ItemStat(name=r[0], count=r[1], total_spent=round(r[2], 2)) for r in rows]


def rename_items_by_name(session: Session, old_name: str, new_name: str) -> int:
    items = session.exec(select(Item).where(Item.name == old_name)).all()
    for item in items:
        item.name = new_name
        session.add(item)
    session.commit()
    return len(items)


def update_item(
    session: Session, receipt_id: int, item_id: int, data: UpdateItemRequest
) -> Item | None:
    item = session.exec(
        select(Item).where(Item.id == item_id, Item.receipt_id == receipt_id)
    ).first()
    if item is None:
        return None
    item.name = data.name.strip()
    item.price = data.price
    item.category = data.category
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def get_distinct_item_names(session: Session) -> list[str]:
    return list(session.exec(select(Item.name).distinct().order_by(Item.name)).all())


def get_receipts_with_items(session: Session) -> list[ReceiptWithItems]:
    receipts_with_items = session.exec(
        select(Receipt)
        .options(selectinload(Receipt.items))  # ty: ignore[invalid-argument-type]
        .order_by(col(Receipt.submitted_at).desc())
    ).all()

    return [
        ReceiptWithItems(
            id=r.id or 0,
            submitted_at=r.submitted_at,
            total=r.total,
            confidence=r.confidence,
            items=[
                ReceiptItem(
                    id=i.id or 0, name=i.name, price=i.price, category=i.category
                )
                for i in r.items
            ],
        )
        for r in receipts_with_items
    ]
