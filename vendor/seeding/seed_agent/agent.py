"""基于无状态循环引擎的 Agent 外观门面。"""

from collections.abc import Callable

import os
import json
import traceback
from seed_ai import UserMessage, TextContent, AssistantMessage
from datetime import datetime

from .types.state import AgentState
from .types.message import AgentMessage
from .types.hooks import AgentHooks
from .types.queue import SteeringQueue
from .types.events import (
    EventEmitter,
    AgentStartEvent,
    AgentEndEvent,
    UserMessageUpdateEvent,
    BaseEvent,
    TurnStartEvent,
    TurnEndEvent,
    ToolCallsStartEvent,
    ToolCallsEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionEndEvent,
    CompressStartEvent,
    CompressEndEvent,
    ErrorEvent,
    AbortEvent,
)
from ._engine.loop import run_agent_loop


def get_type_chain(event) -> str:
    """
    迭代获取 event.type + parent_type 链条
    返回格式：type | parent1 | parent2 | ...
    """
    chain = []
    current = event

    # 循环收集所有 type，直到没有 parent 为止
    while current:
        # 拿到当前节点的 type，加入列表
        chain.append(f"{current.type}.{current.id}")

        # 取下一个 parent（如果没有就停止）
        current = getattr(current, "parent_event", None)  # 安全获取属性

    chain.reverse()
    # 用 | 连接
    # 获取 message 内容：优先 pretty_line()，没有则转 str，如果 message 本身为 None 则为 None
    msg_content = str(getattr(event.message, 'pretty_line', lambda: event.message)()) if event.message else None
    result = " | ".join(chain + ([msg_content] if msg_content else []))
    return f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {result}"

def pretty_line(work_root, event) -> None:
    # 确定保存路径
    file_path = os.path.join(work_root, "events.jsonl")
    event_str = get_type_chain(event)
    
    # 以追加模式 ('a') 写入文件
    with open(file_path, 'a', encoding='utf-8') as f:
        # ensure_ascii=False 可以正常显示中文
        line = json.dumps(event_str, ensure_ascii=False)
        f.write(line + '\n')

    print(work_root, event_str)

class Agent:
    def __init__(
        self,
        initial_state: AgentState,
        hooks: AgentHooks = AgentHooks(),
        parent_event: BaseEvent = BaseEvent()
    ) -> None:
        self.state = initial_state
        self.hooks = hooks
        self._queue = SteeringQueue("one-at-a-time", "one-at-a-time")
        self._emitter = EventEmitter(initial_state.work_root)
        self.parent_event = parent_event

    async def query(self, message: str | UserMessage):
        """主入口：灌入 Prompt，锁定当前智能体并执行 Engine Loop。"""
        if self.state.is_running:
            raise RuntimeError("Agent is already running. Please use .steer() for interruptions.")

        self.state.is_running = True
        self.state.is_aborted = False
        self.state.error = None
        res = None

        # 降维处理，强制转换为 UserMessage
        if isinstance(message, str):
            message = UserMessage(content=[TextContent(text=message)])

        if not isinstance(message, UserMessage):
            raise TypeError("Message must be a string, or UserMessage.")

        try:
            self._emitter.emit(AgentStartEvent(parent_event = self.parent_event))

            # 压入工作窗并保存
            self.state.update_context(message)
            self._emitter.emit(UserMessageUpdateEvent(message = message, parent_event = self.parent_event))

            res = await run_agent_loop(self.state, self._queue, self._emitter, self.hooks, self.parent_event)
            self._emitter.emit(AgentEndEvent(message = res, parent_event = self.parent_event))

        except Exception as e:
            error_stack = traceback.format_exc()
            error_message = AssistantMessage(
                stop_reason=(
                    "aborted" if str(e).lower().find("abort") >= 0 else "error"
                ),
                error_message=error_stack,
            )
            self._emitter.emit(ErrorEvent(message = error_message, parent_event = self.parent_event))

        finally:
            self.state.is_running = False

        return res

    def steer(self, message: str | UserMessage | AgentMessage) -> None:
        """抛入式打断钩子：非阻塞执行，向引擎压入队列。"""
        if isinstance(message, str):
            message = UserMessage(content=[TextContent(text=message)])

        self._queue.steer(message)

    def abort(self, reason: str = "User manually aborted the agent.") -> None:
        """立刻拉下全系统电闸，下发强杀标志位给引擎中的每一个核心阻塞节点。"""
        self.state.is_aborted = True
        self.state.error = reason

    def subscribe(self, handler: Callable | None = None) -> Callable:
        """从底层的事件发射器中订阅颗粒度变化日志。

        Args:
            handler: 事件回调函数，默认为 _default_event_handler。

        Returns:
            一个无参函数，调用后可取消订阅。
        """
        if handler is None:
            handler = pretty_line
        return self._emitter.subscribe(handler)
