import os
from typing import Annotated, cast

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, TextBlock, TextBlockParam
from fastapi import FastAPI, File
from pydantic import BaseModel, ConfigDict

app = FastAPI()

client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

PROMPT = (
    "Extract the receipt contents. For each item, translate abbreviated or coded names to their "
    "generic common name — strip all brand names and return only the product description "
    "(e.g. 'DAWN DISH SOAP' → 'dish soap', 'CHKN BRST' → 'chicken breast', "
    "'PLNT OAT MLK' → 'oat milk', 'CAROLINA BROWN RICE' → 'brown rice'). "
    "Assign a confidence score (0.0–1.0) per item and an overall confidence for the extraction."
)

_FILES_BETA = "files-api-2025-04-14"
_STRUCTURED_BETA = "structured-outputs-2025-11-13"


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


def _media_type(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"GIF8":
        return "image/gif"
    return "image/jpeg"


@app.post("/receipt")
async def handle_receipt(file: Annotated[bytes, File()]):
    uploaded = await client.beta.files.upload(
        file=("receipt", file, _media_type(file)),
        betas=[_FILES_BETA],
    )
    try:
        message = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            extra_headers={"anthropic-beta": f"{_STRUCTURED_BETA},{_FILES_BETA}"},
            extra_body={
                "output_format": {
                    "type": "json_schema",
                    "schema": Output.model_json_schema(),
                }
            },
            messages=cast(list[MessageParam], [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "file", "file_id": uploaded.id}},
                        TextBlockParam(type="text", text=PROMPT),
                    ],
                }
            ]),
        )
    finally:
        await client.beta.files.delete(uploaded.id, betas=[_FILES_BETA])

    block = message.content[0]
    assert isinstance(block, TextBlock)
    return Output.model_validate_json(block.text)