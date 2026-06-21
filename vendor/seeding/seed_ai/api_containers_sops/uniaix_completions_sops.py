"""OpenRouter 专用 Chat Completions 流式选项。

定义 OpenRouter 特有的高级选项，不继承 StreamOptions。
通过 StreamOptions.api_options 传入。
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass
from typing import Any, Literal, cast


class UniaixCompletionsStreamOptions(BaseModel):
    """Uniaix 专用 Chat Completions 流式选项。

    不继承 StreamOptions，通过 StreamOptions.api_options 传入。
    """
    store: bool | None = None
    reasoning_effort: Literal["high", "medium", "low"] | None = None
    n: int | None = None
    max_tokens: int | None = None
    specifyRouter: str | None = None
