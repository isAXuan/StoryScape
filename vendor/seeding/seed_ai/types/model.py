"""模型描述与定价类型定义模块。"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from typing import Any, Literal

from ._provider import Api, Id, Provider


class ModelCost(BaseModel):
    """模型的定价元数据。

    这些值以每百万 Token 的美元 (USD) 表示。它们用于
    计算请求的预估成本，并以与提供商无关的方式公开使用花费信息。

    Attributes:
        input (float): 普通输入 Token 的每百万价格。
        output (float): 模型生成的输出 Token 的每百万价格。
        cacheRead (float): 提示缓存 (prompt-cache) 读取命中 Token 的每百万价格。
        cacheWrite (float): 写入提示缓存 Token 的每百万价格。
    """

    input: float
    output: float
    cacheRead: float
    cacheWrite: float


class Model(BaseModel):
    """一种与提供商无关的可调用模型的统一描述。

    每个请求都从一个 :class:`Model` 开始。该库不要求调用者
    记住特定于提供商的 SDK 客户端配置方式。相反，您提供一个标准化的模型描述，
    然后路由器在内部使用 ``model.api`` 来定位并调用正确的提供商接口。

    Attributes:
        id (str): 提供商原生的模型标识符名称，例如 ``"gpt-4o-mini"``。
        name (str): 用于在日志、UI界面 或调试信息中展示的人类可读名称。
        api (Api): 用于匹配并查找对应提供商实现的路由键（API协议标识）。
        provider (Provider): 模型供应商或服务代理商标签，例如 ``"openai"`` 或 ``"openrouter"``。
        support_reasoning (bool): 该模型是否支持显式的深度推理模式。
        input (list[Literal["text", "image"]]): 模型支持的输入模态列表，通常为 ``["text"]``，多模态模型会包含 ``"image"`` 等。
        cost (ModelCost): 用于追踪和计算成本花销的定价元数据。
        context_window (int): 该模型支持的最大上下文长度 (Token 数量限制)。
        max_tokens (int): 单次请求模型允许生成的最大输出 Token 数量。
    """

    id: Id
    name: str
    api: Api
    provider: Provider
    support_reasoning: bool
    input: list[Literal["text", "image"]]
    cost: ModelCost
    context_window: int
    max_tokens: int
    compress_tokens: int | None = None

    @model_validator(mode='after')
    def __post_init__(self) -> None:
        """实例创建后自动计算 compress_tokens = context_window / 10"""
        # todo 计算何时压缩token
        self.compress_tokens = self.context_window // 100 * 80
        # self.compress_tokens = self.context_window // (1000 * 5)
        return self 
