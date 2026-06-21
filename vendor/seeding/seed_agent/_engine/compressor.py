"""Token 预估与消息压缩模块：在发送给 LLM 前裁剪 context.messages 防止上下文窗口溢出。"""

from __future__ import annotations

from copy import deepcopy
from seed_ai import TextContent
from .llm_stream import llm_stream
from ..types.message import CompressorMessage, AgentMessage, AgentContext
from ..types.state import AgentState
from ..types.events import CompressStartEvent, CompressEndEvent

def split_by_user(messages: list[AgentMessage]) -> list[list[AgentMessage]]:
    result = []
    current = []

    for msg in messages:
        if msg.role == "user":
            if current:
                result.append(current)
            current = [msg]
        else:
            if current:
                current.append(msg)
            # 开头不是 user 的消息直接丢弃

    if current:
        result.append(current)

    return result


# ─── 压缩逻辑 ──────────────────────────────────────────────────────────────
async def compress_messages(state: AgentState, emitter, parent_event) -> bool:
    """检查 context.messages 的 token 估算是否超出模型窗口，超出则裁剪。

    压缩策略：保留第一条 user message（建立初始上下文）+ 从尾部往前尽可能多地保留最新消息。

    Returns:
        True 如果发生了压缩，False 如果无需压缩。
    """
    new_state = deepcopy(state)
    new_state.model_options.tool_choice = "auto"

    messages = new_state.context.messages
    user_series_messages = split_by_user(messages)
    compress_range = (0, len(messages) - len(user_series_messages[-1]))

    messages_compressed = messages[compress_range[0]:compress_range[1]]
    messages_reset = messages[compress_range[1]:]


    user_message = CompressorMessage(content=[TextContent(text="请将历史聊天内容进行压缩")])
    compress_start_event = CompressStartEvent(parent_event = parent_event)
    emitter.emit(compress_start_event)
    new_state.context = AgentContext(
        system="你是一个内容压缩小助手",
        messages=messages_compressed + [user_message]
    )
    result = await llm_stream(new_state, emitter, compress_start_event)

    new_messages: list[AgentMessage] = []
    if result:
        new_messages.append(user_message)
        new_messages.append(result)
        new_messages.extend(messages_reset)
        state.update_context(new_messages, compress_range=compress_range)
        emitter.emit(CompressEndEvent(parent_event = parent_event))
        return True

    emitter.emit(CompressEndEvent(parent_event = parent_event))
    return False
