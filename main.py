import base64
import io
import os
from typing import Annotated

from anthropic import AsyncAnthropic
from anthropic.types import (
    Base64ImageSourceParam,
    ImageBlockParam,
    MessageParam,
    TextBlock,
    TextBlockParam,
)
from fastapi import FastAPI, File
from PIL import Image, ImageOps  # type: ignore[import-untyped]
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


_MAX_BYTES = 5 * 1024 * 1024  # 5 MB API limit


def _compress(data: bytes) -> bytes:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")  # type: ignore[union-attr]
    for quality in range(95, 15, -10):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        result = buf.getvalue()
        if len(result) <= _MAX_BYTES:
            return result
    # Still too large — scale down proportionally and encode at q=85
    scale = (_MAX_BYTES / len(data)) ** 0.5
    img = img.resize(
        (int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS
    )  # type: ignore[attr-defined]
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


@app.post("/receipt")
async def handle_receipt(file: Annotated[bytes, File()]):
    image_bytes = _compress(file)
    image_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    message = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        extra_headers={"anthropic-beta": "structured-outputs-2025-11-13"},
        extra_body={
            "output_format": {
                "type": "json_schema",
                "schema": Output.model_json_schema(),
            }
        },
        messages=[
            MessageParam(
                role="user",
                content=[
                    ImageBlockParam(
                        type="image",
                        source=Base64ImageSourceParam(
                            type="base64",
                            media_type="image/jpeg",
                            data=image_data,
                        ),
                    ),
                    TextBlockParam(type="text", text=PROMPT),
                ],
            )
        ],
    )

    block = message.content[0]
    assert isinstance(block, TextBlock)
    return Output.model_validate_json(block.text)
