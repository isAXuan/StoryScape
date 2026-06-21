from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass
from typing import Literal, Optional, Any
from datetime import datetime
import uuid

from .message import AssistantMessage, ToolCall

class BaseEvent(BaseModel):
    """所有事件的基类"""
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    type: str = "root"
    parent_event: Optional[BaseEvent] = None
    message: Optional[Any] = None
    details: Optional[dict] = None

    def pretty_line(self) -> str:
        """返回格式化的日志字符串"""
        parts = [f"[{self.timestamp}] {self.type} id={self.id}"]
        if self.parent_event:
            parts.append(f"parent={self.parent_event.id}")
        if self.details:
            parts.append(f"details={self.details}")
        return " ".join(parts)


class StartEvent(BaseEvent):
    """流式生成开始时触发的事件。

    Attributes:
        type (Literal["start"]): 事件类型标识。
        message (AssistantMessage): 初始化的、仍处于不完整状态的助手消息对象。
    """

    message: AssistantMessage
    type: Literal["start"] = "start"

    def pretty_line(self) -> str:
        return f"{super().log()} message.role={self.message.role}"


class TextStartEvent(BaseEvent):
    """文本内容块开始生成事件。"""

    contentIndex: int
    message: AssistantMessage
    type: Literal["text_start"] = "text_start"

    def pretty_line(self) -> str:
        return f"{super().log()} contentIndex={self.contentIndex}"


class TextDeltaEvent(BaseEvent):
    """文本内容块增量更新事件。"""

    contentIndex: int
    delta: str
    message: AssistantMessage
    type: Literal["text_delta"] = "text_delta"

    def pretty_line(self) -> str:
        text = self.delta[:50] + "..." if len(self.delta) > 50 else self.delta
        return f"{super().log()} contentIndex={self.contentIndex} delta={text!r}"


class TextEndEvent(BaseEvent):
    """文本内容块生成结束事件。"""

    contentIndex: int
    content: str
    message: AssistantMessage
    type: Literal["text_end"] = "text_end"

    def pretty_line(self) -> str:
        text = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{super().log()} contentIndex={self.contentIndex} content={text!r}"


class ThinkingStartEvent(BaseEvent):
    """思考/推理内容开始生成事件。"""

    contentIndex: int
    message: AssistantMessage
    type: Literal["thinking_start"] = "thinking_start"

    def pretty_line(self) -> str:
        return f"{super().log()} contentIndex={self.contentIndex}"


class ThinkingDeltaEvent(BaseEvent):
    """思考/推理内容增量更新事件。"""

    contentIndex: int
    delta: str
    message: AssistantMessage
    type: Literal["thinking_delta"] = "thinking_delta"

    def pretty_line(self) -> str:
        text = self.delta[:50] + "..." if len(self.delta) > 50 else self.delta
        return f"{super().log()} contentIndex={self.contentIndex} delta={text!r}"


class ThinkingEndEvent(BaseEvent):
    """思考/推理内容生成结束事件。"""

    contentIndex: int
    content: str
    message: AssistantMessage
    type: Literal["thinking_end"] = "thinking_end"

    def pretty_line(self) -> str:
        text = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{super().log()} contentIndex={self.contentIndex} content={text!r}"


class ToolCallStartEvent(BaseEvent):
    """工具调用内容块开始事件。"""

    contentIndex: int
    message: AssistantMessage
    type: Literal["toolcall_start"] = "toolcall_start"

    def pretty_line(self) -> str:
        return f"{super().log()} contentIndex={self.contentIndex}"


class ToolCallDeltaEvent(BaseEvent):
    """工具调用参数增量更新事件。"""

    contentIndex: int
    delta: str
    message: AssistantMessage
    type: Literal["toolcall_delta"] = "toolcall_delta"

    def pretty_line(self) -> str:
        text = self.delta[:50] + "..." if len(self.delta) > 50 else self.delta
        return f"{super().log()} contentIndex={self.contentIndex} delta={text!r}"


class ToolCallEndEvent(BaseEvent):
    """工具调用内容块结束事件。"""

    contentIndex: int
    toolCall: ToolCall
    message: AssistantMessage
    type: Literal["toolcall_end"] = "toolcall_end"

    def pretty_line(self) -> str:
        return f"{super().log()} contentIndex={self.contentIndex} toolCall={self.toolCall.name}"


class DoneEvent(BaseEvent):
    """流式生成成功结束的最终事件。

    Attributes:
        type (Literal["done"]): 事件类型标识。
        reason (Literal["stop", "length", "toolUse"]): 模型停止生成的原因。
        message (AssistantMessage): 最终组装完整的助手消息对象。
    """

    reason: Literal["stop", "length", "toolUse"]
    message: AssistantMessage
    type: Literal["done"] = "done"

    def pretty_line(self) -> str:
        return f"{super().log()} reason={self.reason}"


class ErrorEvent(BaseEvent):
    """流式生成中途失败或被强行中断的事件。

    Attributes:
        type (Literal["error"]): 事件类型标识。
        reason (Literal["aborted", "error"]): 失败的中断原因或错误状态。
        error (AssistantMessage): 包含已生成部分内容的助手消息。
    """

    reason: Literal["aborted", "error"]
    message: AssistantMessage
    type: Literal["error"] = "error"

    def pretty_line(self) -> str:
        return f"{super().log()} reason={self.reason}"


# 将所有的助手消息流式事件汇聚为一个联合类型，用于输入输出的类型提示
AssistantMessageEvent = (
    StartEvent
    | TextStartEvent
    | TextDeltaEvent
    | TextEndEvent
    | ThinkingStartEvent
    | ThinkingDeltaEvent
    | ThinkingEndEvent
    | ToolCallStartEvent
    | ToolCallDeltaEvent
    | ToolCallEndEvent
    | DoneEvent
    | ErrorEvent
)

BaseEvent.model_rebuild()
