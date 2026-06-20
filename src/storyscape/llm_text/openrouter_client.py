import json
import sys
from pathlib import Path

from json_repair import repair_json

from storyscape.llm_text.schemas import TextAnnotationResult
from storyscape.settings import get_settings


def _ensure_vendor_path() -> None:
    root = Path(__file__).resolve().parents[3]
    vendor_path = root / "vendor" / "seeding"
    if str(vendor_path) not in sys.path:
        sys.path.insert(0, str(vendor_path))


async def complete_json(prompt: str) -> tuple[TextAnnotationResult, str]:
    _ensure_vendor_path()
    from seed_ai import Model, ModelCost, ModelOptions, StreamOptions, TextContent, UserMessage, complete
    from seed_ai.types import Context
    from seed_ai.types.options import ResponseFormat

    settings = get_settings()
    model = Model(
        id=settings.openrouter_model,
        name=settings.openrouter_model,
        api="openrouter-completions",
        provider="openrouter",
        support_reasoning=False,
        input=["text"],
        cost=ModelCost(input=0, output=0, cacheRead=0, cacheWrite=0),
        context_window=128000,
        max_tokens=8192,
    )
    message = await complete(
        model,
        Context(
            system="Return strict JSON only. Do not include markdown fences.",
            messages=[UserMessage(content=[TextContent(text=prompt)])],
        ),
        StreamOptions(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
        ),
        ModelOptions(response_format=ResponseFormat(type="json_object")),
    )
    if message.stop_reason == "error":
        raise RuntimeError(message.error_message or "OpenRouter request failed")

    raw = "".join(
        getattr(block, "text", "")
        for block in message.content
        if getattr(block, "type", "") == "text"
    )
    if not raw:
        raise ValueError("Model returned no text content")
    return parse_annotation_json(raw), raw


def parse_annotation_json(raw: str) -> TextAnnotationResult:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        repaired = repair_json(raw)
        data = json.loads(repaired)
    return TextAnnotationResult.model_validate(data)
