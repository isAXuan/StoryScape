"""提供纯粹的发布-订阅模式，用于解耦细粒度事件广播大喇叭。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional
from seed_ai import AssistantMessageEvent, BaseEvent


# ─── AI Events (包装 seed_ai 事件) ──────────────────────────────────────────────
LLMStreamEvent = AssistantMessageEvent

# ─── Agent Lifecycle Events ───────────────────────────────────────────────────

class AgentStartEvent(BaseEvent):
    type: str = "agent_start"

class AgentEndEvent(BaseEvent):
    type: str = "agent_end"

# ─── Loop Events ───────────────────────────────────────────────────────────────

class LoopStartEvent(BaseEvent):
    type: str = "loop_start"

class LoopEndEvent(BaseEvent):
    type: str = "loop_end"

# ─── Turn Events ───────────────────────────────────────────────────────────────

class TurnStartEvent(BaseEvent):
    type: str = "turn_start"

class TurnEndEvent(BaseEvent):
    type: str = "turn_end"

# ─── User Input Events ─────────────────────────────────────────────────────────

class UserMessageUpdateEvent(BaseEvent):
    type: str = "user_message_update"

class QueueMessageUpdateEvent(BaseEvent):
    type: str = "queue_message_update"

# ─── Tool Execution Events ─────────────────────────────────────────────────────

class ToolCallsStartEvent(BaseEvent):
    type: str = "tool_calls_start"

class ToolExecutionStartEvent(BaseEvent):
    type: str = "tool_execution_start"

class ToolExecutionEndEvent(BaseEvent):
    type: str = "tool_execution_end"

class ToolCallsEndEvent(BaseEvent):
    type: str = "tool_calls_end"

# ─── Compress Events ───────────────────────────────────────────────────────────

class CompressStartEvent(BaseEvent):
    type: str = "compress_start"

class CompressEndEvent(BaseEvent):
    type: str = "compress_end"

# ─── Abort Events ──────────────────────────────────────────────────────────────

class AbortEvent(BaseEvent):
    type: str = "abort"


class ErrorEvent(BaseEvent):
    type: str = "error"

# ─── Union Type ────────────────────────────────────────────────────────────────

AgentEvent = (
    AgentStartEvent | AgentEndEvent
    | LoopStartEvent | LoopEndEvent
    | TurnStartEvent | TurnEndEvent
    | UserMessageUpdateEvent | QueueMessageUpdateEvent
    | ToolCallsStartEvent | ToolExecutionStartEvent | ToolExecutionEndEvent | ToolCallsEndEvent
    | CompressStartEvent | CompressEndEvent
    | AbortEvent | ErrorEvent
)

# ─── EventEmitter ─────────────────────────────────────────────────────────────

class EventEmitter:

    def __init__(self, work_root: str) -> None:
        self._listeners: set[Callable[[AgentEvent], None]] = set()
        self._current_parent: Optional[BaseEvent] = None
        self.work_root = work_root

    def subscribe(self, callback: Callable[[AgentEvent| LLMStreamEvent], None]) -> Callable[[], None]:
        """订阅 Agent 运行事件。

        Args:
            callback: 接收 `AgentEvent` 的回调函数。

        Returns:
            一个无参函数，调用后可取消订阅。
        """
        self._listeners.add(callback)

        def unsubscribe() -> None:
            self._listeners.discard(callback)

        return unsubscribe

    def emit(self, event: AgentEvent | LLMStreamEvent) -> None:
        """向所有订阅者广播一个事件。"""
        # 向所有订阅者广播
        for listener in list(self._listeners):
            listener(self.work_root, event)

BaseEvent.model_rebuild()

