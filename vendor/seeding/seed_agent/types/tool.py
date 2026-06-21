"""具有本地执行能力边界的智能工具模块。"""

from __future__ import annotations

import inspect
import re
from datetime import datetime
from typing import Any, TYPE_CHECKING, get_type_hints

from pydantic import BaseModel

from seed_ai import Tool, ToolResultMessage, TextContent

if TYPE_CHECKING:
    from .message import AgentContext


# ─── 内部工具函数 ────────────────────────────────────────────────────────────

def _camel_to_snake(name: str) -> str:
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


_PY_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _parse_sig(fn) -> tuple[type | None, dict, bool]:
    """解析函数签名，返回 (pydantic_cls, json_schema, is_flat)。

    - Pydantic 模式：只有一个参数（非 self），且类型是 BaseModel 子类
    - Flat 模式：多个参数，或单参数但非 BaseModel
    """
    hints = get_type_hints(fn)
    sig = inspect.signature(fn)
    param_names = [p for p in sig.parameters if p not in ("self", "cls")]

    # Pydantic 模式
    if len(param_names) == 1:
        candidate = hints.get(param_names[0])
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            schema = dict(candidate.model_json_schema())
            schema.pop("title", None)
            return candidate, schema, False

    # Flat 模式
    properties: dict[str, dict] = {}
    required: list[str] = []
    for pname in param_names:
        ptype = hints.get(pname, str)
        properties[pname] = {
            "type": _PY_TO_JSON.get(ptype, "string"),
            "description": pname,
        }
        if sig.parameters[pname].default is inspect.Parameter.empty:
            required.append(pname)

    return None, {"type": "object", "properties": properties, "required": required}, True


# ─── @tools 装饰器 ──────────────────────────────────────────────────────────

def tools(fn):
    """将一个 async 函数直接转为 AgentTool 实例。

    支持两种签名风格：

    风格一 — 单 Pydantic BaseModel，call 收到反序列化后的 model 实例::

        @tools
        async def echo(params: EchoParameters) -> str:
            return f"echoed: {params.value}"   # params 是 EchoParameters 实例

    风格二 — 扁平 Python 类型，call 收到展开的具名 kwargs::

        @tools
        async def add(a: int, b: int) -> str:
            return f"{a} + {b} = {a + b}"     # a, b 已经是 int

    两种风格都会自动推导 name / description / parameters，
    生成的对象可以直接放进 context.tools 列表。
    """
    pydantic_cls, schema, is_flat = _parse_sig(fn)
    tool_name = fn.__name__
    tool_desc = (inspect.getdoc(fn) or "").strip()

    async def _call(self, params):
        if pydantic_cls is not None and isinstance(params, dict):
            return await fn(pydantic_cls(**params))
        elif is_flat and isinstance(params, dict):
            return await fn(**params)
        else:
            return await fn(params)

    # 标记此类由 @tools 生成，execute 不应再解析签名做二次拆包
    _call._tools_generated = True
    tool_cls = type(f"_{tool_name}_Tool", (AgentTool,), {"call": _call})
    return tool_cls(name=tool_name, description=tool_desc, parameters=schema)


# ─── AgentTool 基类 ─────────────────────────────────────────────────────────

class AgentTool(Tool):
    """挂载了 `execute` 本地钩子反射能力的底层基类，供所有业务子工具派生。

    架构分层：
        - `call(...)` — **对内**：实现核心业务逻辑，可独立单元测试。
        - `execute(...)` — **对外**：引擎专用入口，桥接 call() 返回 ToolResultMessage。

    无需手写 __init__，所有元信息自动从 call 签名推导：
        - name        ← 类名去掉 'Tool' 后缀，转 snake_case
        - description ← call 方法的 docstring → class docstring
        - parameters  ← Pydantic model schema 或 flat 参数注解 schema

    对于 class 协议（无 @tools），call 接收的类型取决于签名：
        - params: BaseModel 签名 → call 收到 raw dict（自行处理，如 params["key"]）
        - a: int, b: dict 签名 → execute 自动拆包，call 直接收到具名参数
    """

    def __init__(
        self,
        name: str = "",
        description: str = "",
        parameters: Any = None,
        **kwargs
    ):
        call_fn = getattr(type(self), 'call', None)

        if call_fn and call_fn is not AgentTool.call:
            if not name:
                cls_name = type(self).__name__
                bare = cls_name.removesuffix('Tool') or cls_name
                name = _camel_to_snake(bare)

            if not description:
                description = (inspect.getdoc(call_fn) or '').strip()
                if not description:
                    description = (inspect.getdoc(type(self)) or '').strip()

            if parameters is None:
                _, parameters, _ = _parse_sig(call_fn)

        super().__init__(
            name=name,
            description=description,
            parameters=parameters or {},
            **kwargs
        )

    async def call(self, params: Any) -> str:
        """子类覆盖此方法实现核心业务逻辑。可独立测试，无需 tool_call_id/context。"""
        raise NotImplementedError("Subclasses must implement the call() method.")

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        context: 'AgentContext',
    ) -> ToolResultMessage:
        """对外引擎调度入口：桥接 call() 并包装为合规的 ToolResultMessage。

        class 协议 dispatch 规则（无 @tools 时）：
            - Pydantic 签名 → 直接传 raw dict 给 call（用户自行处理）
            - Flat 签名     → 自动拆包 dict 为具名 kwargs 再传给 call
        """
        call_fn = type(self).call
        is_generated = getattr(call_fn, '_tools_generated', False)

        if not is_generated:
            # class 协议：透过原始签名判断是否需要拆包
            _, _, is_flat = _parse_sig(call_fn)
            if is_flat and isinstance(params, dict):
                result_text = await call_fn(self, **params)
            else:
                result_text = await self.call(params)
        else:
            # @tools 生成的类：_call 内部已经处理好 dispatch，直接调用
            result_text = await self.call(params)

        return ToolResultMessage(
            tool_call_id=tool_call_id,
            tool_name=self.name,
            content=[TextContent(text=str(result_text))],
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )


    async def hook(self, event: dict) -> None:
        """子类覆盖此方法实现事件钩子。可独立测试，无需 tool_call_id/context。"""
        raise NotImplementedError("Subclasses must implement the hook() method.")