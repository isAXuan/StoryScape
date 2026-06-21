"""API 类型与标识符定义模块。

包含：
- Provider 流函数类型别名
- ApiContainer 相关类定义
"""

from __future__ import annotations

from collections.abc import Callable
from pydantic import BaseModel, Field, ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass

from ._provider import Api
from .model import Model
from .message import Context
from .options import ModelOptions, StreamOptions
from ._stream import AssistantMessageEventStream


# ============ Provider 函数类型 ============

ApiStreamFunction = Callable[
    [Model, Context, StreamOptions, ModelOptions | None], AssistantMessageEventStream
]


# ============ Container 类定义 ============

class ApiContainer(BaseModel):
    """代表一个合规注册入驻的 API 提供商实体结构定义规范包，涵盖了全套生命周期控制发包流函数。"""

    api: Api
    stream: ApiStreamFunction