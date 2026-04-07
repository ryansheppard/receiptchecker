import hashlib
import os
from datetime import date
from typing import cast

import gspread
import polars as pl
import redis.asyncio as redis
from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, TextBlock, TextBlockParam
from fastapi import FastAPI, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

_FILES_BETA = "files-api-2025-04-14"

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

anthropic_client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

sheets_client = gspread.service_account()

redis_client = redis.Redis()


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float
    category: str
    raw: str
    confidence: float


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: float
    items: list[Item]
    confidence: float


TRANSCRIBE_PROMPT = (
    "Transcribe this receipt verbatim, preserving the exact layout including line breaks, "
    "spacing, and all characters. Do not interpret or summarize — output the raw text only."
)

PARSE_PROMPT = (
    "Parse the following receipt text into structured data. For each item, translate abbreviated "
    "or coded names to their generic common name — strip all brand names and return only the "
    "product description (e.g. 'DAWN DISH SOAP' → 'dish soap', 'CHKN BRST' → 'chicken breast', "
    "'PLNT OAT MLK' → 'oat milk', 'CAROLINA BROWN RICE' → 'brown rice'). "
    "Some items span two lines: the item name appears on one line with no price, and the next line "
    "shows 'N @ unit_price  total' — this is one item whose price is the TOTAL (the rightmost "
    "number on the second line), not the unit price. Do not emit a separate item for the quantity "
    "line. "
    "Include savings and discounts (e.g. loyalty rewards, coupons) as items with negative prices "
    "and include sales tax as an item with a positive price, so the item prices sum to the receipt total. "
    "Assign a confidence score (0.0–1.0) per item and an overall confidence for the extraction.\n\n"
    "Receipt text:\n"
)


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.post("/receipt")
async def handle_receipt(file: UploadFile):
    data = await file.read()
    digest = hashlib.sha256(data).hexdigest()
    value = await redis_client.get(digest)
    if value:
        return Output.model_validate_json(value)

    uploaded = await anthropic_client.beta.files.upload(
        file=("receipt", data, file.content_type),
        betas=[_FILES_BETA],
    )
    try:
        transcription = await anthropic_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2048,
            extra_headers={"anthropic-beta": _FILES_BETA},
            messages=cast(
                list[MessageParam],
                [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {"type": "file", "file_id": uploaded.id},
                            },
                            TextBlockParam(type="text", text=TRANSCRIBE_PROMPT),
                        ],
                    }
                ],
            ),
        )
    finally:
        await anthropic_client.beta.files.delete(uploaded.id, betas=[_FILES_BETA])

    raw_text = cast(TextBlock, transcription.content[0]).text

    message = await anthropic_client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        extra_body={
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "schema": Output.model_json_schema(),
                }
            }
        },
        messages=cast(
            list[MessageParam],
            [
                {
                    "role": "user",
                    "content": [
                        TextBlockParam(type="text", text=PARSE_PROMPT + raw_text),
                    ],
                }
            ],
        ),
    )

    block = cast(TextBlock, message.content[0])
    output = Output.model_validate_json(block.text)
    await redis_client.set(digest, output.model_dump_json(), 3600)
    return output


@app.post("/submit")
async def handle_submit(output: Output):
    today = date.today()
    sh = sheets_client.open("Receipt Checker")
    ws = sh.worksheet("raw")
    is_empty = not any(ws.row_values(1))
    df = pl.DataFrame(
        [item.model_dump(exclude={"confidence"}) for item in output.items]
    ).with_columns(pl.lit(today).alias("date"))
    rows = [
        [v if isinstance(v, (int, float)) else str(v) for v in row] for row in df.rows()
    ]
    if is_empty:
        rows = [df.columns] + rows
    ws.append_rows(rows)
    return {"url": sh.url}
