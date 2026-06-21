"""OpenRouter 专用 Chat Completions 流式选项。

定义 OpenRouter 特有的高级选项，不继承 StreamOptions。
通过 StreamOptions.api_options 传入。
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass
from typing import Any, Literal, cast


class CacheControl(BaseModel):
    """缓存控制选项。"""
    type: Literal["ephemeral"]
    ttl: Literal["5m", "1h"] | None = None


class Debug(BaseModel):
    """调试选项，用于检查请求转换 (仅流式模式)。"""
    echo_upstream_body: bool | None = None

class ReasoningConfig(BaseModel):
    """推理配置，用于控制推理模型的行为。"""
    effort: Literal["xhigh", "high", "medium", "low", "minimal", "none"] | None = None
    summary: Literal["auto", "concise", "detailed"] | None = None

# === Verbosity 类型 ===
VerbosityLevel = Literal["low", "medium", "high", "max"]

class OpenRouterCompletionsStreamOptions(BaseModel):
    """OpenRouter 专用 Chat Completions 流式选项。

    不继承 StreamOptions，通过 StreamOptions.api_options 传入。

        top_k (int | None): Top-K 采样令牌数。
        min_p (float | None): 最小令牌概率阈值。
        top_a (float | None): 动态 Top-P 阈值。
        repetition_penalty (float | None): 重复惩罚。
        response_format (ResponseFormat | None): 响应格式。
        verbosity (VerbosityLevel | None): 响应详细程度。、
    """
    top_k: int | None = None
    min_p: float | None = None
    top_a: float | None = None
    repetition_penalty: float | None = None
    structured_outputs: bool | None = None
    verbosity: VerbosityLevel | None = None

    # 缓存控制，支持 {type: "ephemeral", ttl?: "5m"|"1h"}
    cache_control: CacheControl | None = None
    # 调试选项，用于检查请求转换 (仅流式模式)
    # 支持 echo_upstream_body: true - 在流开始时输出上游请求体
    debug: Debug | None = None
    # 插件配置列表，目前好像用不上，暂时不学习配置 # Todo
    # plugins: list[Plugin] | None = None
    # 推理配置，用于控制推理模型的行为
    reasoning: ReasoningConfig | None = None
    # 路由选项，控制请求路由行为
    route: dict[str, object] | None = None
    # 服务层级，用于控制请求处理优先级
    service_tier: Literal["auto", "default", "flex", "priority", "scale"] | None = None