import os
from datetime import date
from typing import Annotated, cast

import gspread
import polars as pl
from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, TextBlock, TextBlockParam
from fastapi import FastAPI, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

_FILES_BETA = "files-api-2025-04-14"

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

sheets_client = gspread.service_account()


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
async def handle_receipt(file: Annotated[bytes, File()]):
    uploaded = await client.beta.files.upload(
        file=("receipt", file, _media_type(file)),
        betas=[_FILES_BETA],
    )
    try:
        transcription = await client.messages.create(
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
        await client.beta.files.delete(uploaded.id, betas=[_FILES_BETA])

    raw_text = cast(TextBlock, transcription.content[0]).text

    message = await client.messages.create(
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
    return Output.model_validate_json(block.text)


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


def _media_type(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"GIF8":
        return "image/gif"
    return "image/jpeg"
