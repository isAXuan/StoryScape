"""流式选项与推理控制类型定义模块。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pydantic import BaseModel, Field, ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass
from typing import Any, Literal, TypeAlias, TYPE_CHECKING


from .model import Model
from ..api_containers_sops.openrouter_completions_sops import OpenRouterCompletionsStreamOptions
from ..api_containers_sops.uniaix_completions_sops import UniaixCompletionsStreamOptions

# 模型停止生成内容的原因
StopReason = Literal["stop", "length", "toolUse", "error", "aborted"]


# === Response Format 类型 ===
ResponseFormatType = Literal["text", "json_object", "json_schema", "grammar", "python"]


class JsonSchemaObject(BaseModel):
    """JSON Schema 配置对象"""
    name: str  # <=64 chars: a-z, A-Z, 0-9, underscores, dashes
    description: str | None = None
    schema: dict[str, Any] | None = None
    strict: bool | None = None


class ResponseFormat(BaseModel):
    """响应格式配置，支持 5 种格式变体。

    Variants:
        text: {"type": "text"} - 纯文本格式，默认
        json_object: {"type": "json_object"} - JSON 对象格式
        json_schema: {"type": "json_schema", "json_schema": {...}} - JSON Schema 约束格式
        grammar: {"type": "grammar", "grammar": "..."} - 自定义语法约束
        python: {"type": "python"} - Python 代码格式
    """
    type: ResponseFormatType
    json_schema: JsonSchemaObject | None = None
    grammar: str | None = None


# === Tool Choice 类型 ===
ToolChoiceMode = Literal["auto", "none", "required"]

class FunctionObject(BaseModel):
    """工具函数对象"""
    name: str


class ToolChoiceFunction(BaseModel):
    """工具选择函数配置"""
    function: FunctionObject
    type: Literal["function"] = "function"


# === API 选项类型 ===
# 提供商特有的选项联合类型
ApiOptions = OpenRouterCompletionsStreamOptions | UniaixCompletionsStreamOptions


# === StreamOptions：客户端配置层 ===
class StreamOptions(BaseModel):
    """客户端配置层，包含连接、认证和传输相关配置。

    Attributes:
        base_url (str): 模型提供商的基础 HTTP 端点接口地址。
        api_key (str | None): API 密钥。
        headers (dict[str, str] | None): 额外合并到 HTTP 请求中的自定义请求头。
        hook (Callable | None): 可选的钩子回调，可以在发送 HTTP 请求前检查或重写载荷。
        metadata (dict[str, Any] | None): 附加元数据。
        timeout (float | None): HTTP 请求超时秒数；None 表示不限制超时（推荐用于流式长推理模型）。
    """

    base_url: str
    api_key: str
    headers: dict[str, str] | None = None
    hook: Callable | None = None
    metadata: dict[str, Any] | None = None
    timeout: float | None = None


# === ModelOptions：AI 载荷层 ===
class ModelOptions(BaseModel):
    """AI 载荷层，包含采样参数、工具调用和输出格式配置。

    Attributes:
        temperature (float | None): 模型采样温度，控制输出的随机性。
        top_p (float | None): Nucleus 采样阈值。
        frequency_penalty (float | None): 频率惩罚。
        presence_penalty (float | None): 存在惩罚。
        seed (int | None): 随机种子。
        max_completion_tokens (int | None): 最大完成令牌数。
        logit_bias (dict[int, float] | None): 令牌概率偏置。
        logprobs (bool): 是否返回对数概率。
        top_logprobs (int | None): 每个位置的 top logprobs。
        structured_outputs (bool | None): 结构化输出。
        stream_options (dict): 流式选项。
        stop (list[str] | None): 停止序列。
        tool_choice (ToolChoiceMode | ToolChoiceFunction | None): 工具选择策略。
        parallel_tool_calls (bool | None): 是否允许并行工具调用。
        api_options (ApiOptions | None): 提供商特定选项。
    """

    # === Sampling 参数 ===
    temperature: float | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    seed: int | None = None

    # === Token 限制 ===
    max_completion_tokens: int | None = None

    # === Logit 相关 ===
    logit_bias: dict[int, float] | None = None
    logprobs: bool = False
    top_logprobs: int | None = None

    # === 输出格式 ===
    response_format: ResponseFormat | None = None
    stream_options: dict[str, bool] = Field(default_factory=lambda: {"include_usage": True})

    # === 停止条件 ===
    stop: list[str] | None = None

    # === 工具调用 ===
    tool_choice: ToolChoiceMode | ToolChoiceFunction | None = None
    parallel_tool_calls: bool | None = None

    # === 提供商特有选项 ===
    api_options: ApiOptions | None = Field(default=None, json_schema_extra={"unfold": True})

    def to_payload(self, params_rules: list[str]) -> dict:
        """转换为 API 载荷字典。

        Args:
            params_rules: OpenAI SDK 支持的参数名列表。

        Returns:
            分离后的载荷字典，rules 内的放顶层，其余放 extra_body。
        """
        src_payload = clean(self)

        params_set = set(params_rules)
        payload = {k: v for k, v in src_payload.items() if k in params_set}
        extra = {k: v for k, v in src_payload.items() if k not in params_set}
        if extra:
            payload["extra_body"] = extra

        return payload


def clean(obj: Any, parent_folded: bool = False) -> Any:
    """
    基于元数据标记过滤的递归转换函数

    Args:
        obj: 待处理对象
        parent_folded: 标记上层是否要求展开（unfold），若为 True 则本层结果直接返回不做为顶层键
    """
    if isinstance(obj, BaseModel):
        result = {}
        for name, field_info in obj.model_fields.items():
            if field_info.exclude:
                continue
            value = getattr(obj, name)
            if value is None:
                continue
            if field_info.json_schema_extra and field_info.json_schema_extra.get("unfold"):
                unfolded = clean(value, parent_folded=True)
                if isinstance(unfolded, dict):
                    result.update(unfolded)
            else:
                result[name] = clean(value)
        return result

    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items() if v is not None}

    if isinstance(obj, (list, tuple)):
        return [clean(x) for x in obj if x is not None]

    return obj