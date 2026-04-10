import hashlib

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from app.anthropic import parse_receipt, redis_client
from app.database import engine
from app.models import Item, ParsedItem, ParsedReceipt, Receipt

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
