import os
from typing import cast

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, TextBlock, TextBlockParam

from app.models import ParsedReceipt

anthropic_client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

_FILES_BETA = "files-api-2025-04-14"

_TRANSCRIBE_PROMPT = (
    "Transcribe this receipt verbatim, preserving the exact layout including line breaks, "
    "spacing, and all characters. Do not interpret or summarize — output the raw text only."
)

_PARSE_PROMPT = (
    "Parse the following receipt text into structured data. For each item, translate abbreviated "
    "or coded names to their generic common name — strip all brand names and return only the "
    "product description (e.g. 'DAWN DISH SOAP' → 'dish soap', 'CHKN BRST' → 'chicken breast', "
    "'PLNT OAT MLK' → 'oat milk', 'CAROLINA BROWN RICE' → 'brown rice'). "
    "Some items span two lines: the item name appears on one line with no price, and the next line "
    "shows 'N @ unit_price  total' — emit N separate items each with the unit price (the number "
    "after '@'), not the total. "
    "Include savings and discounts (e.g. loyalty rewards, coupons) as items with negative prices "
    "and include sales tax as an item with a positive price, so the item prices sum to the receipt total. "
    "Assign a confidence score (0.0–1.0) per item and an overall confidence for the extraction.\n\n"
    "Receipt text:\n"
)


async def parse_receipt(data: bytes, content_type: str) -> ParsedReceipt:
    uploaded = await anthropic_client.beta.files.upload(
        file=("receipt", data, content_type),
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
                            TextBlockParam(type="text", text=_TRANSCRIBE_PROMPT),
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
                    "schema": ParsedReceipt.model_json_schema(),
                }
            }
        },
        messages=cast(
            list[MessageParam],
            [
                {
                    "role": "user",
                    "content": [
                        TextBlockParam(type="text", text=_PARSE_PROMPT + raw_text),
                    ],
                }
            ],
        ),
    )

    block = cast(TextBlock, message.content[0])
    return ParsedReceipt.model_validate_json(block.text)
