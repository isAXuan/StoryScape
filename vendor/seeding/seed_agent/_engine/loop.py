"""心脏打火机：串联发送、收流与工具拦截递归的闭包协程。"""

from ..types.state import AgentState
from ..types.hooks import AgentHooks
from ..types.queue import SteeringQueue
from ..types.events import (
    EventEmitter,
    TurnStartEvent,
    TurnEndEvent,
    QueueMessageUpdateEvent,
    BaseEvent
)
from .llm_stream import llm_stream
from .executor import execute_tool_calls
from .compressor import compress_messages

async def run_agent_loop(
    state: AgentState,
    queue: SteeringQueue,
    emitter: EventEmitter,
    hooks: AgentHooks,
    parent_event: BaseEvent
) -> None:
    """一脚踹入大满贯无限流状态，不到工具用完或外部信号死不回头。"""

    state.max_auto_turn = AgentState.model_fields['max_auto_turn'].default
    state.cur_turn = 0
    message = None

    state = await hooks.loop_before(state)

    while True:
        if state.is_aborted:
            break

        state.cur_turn += 1
        turn_event = TurnStartEvent(parent_event = parent_event)

        emitter.emit(turn_event)
        state = await hooks.turn_start(state)

        # 1. 插队网拦截检查
        pending_steer_msgs = queue.dequeue_steering_messages()
        if pending_steer_msgs:
            for p_msg in pending_steer_msgs:
                state.update_context(p_msg)
                state = await hooks.user_update_before(state)
                emitter.emit(QueueMessageUpdateEvent(parent_event = turn_event))
                state = await hooks.user_update_after(p_msg)

        # 2. AI大模型响应下一步
        state = await hooks.llm_stream_before(state)
        message = await llm_stream(state, emitter, turn_event)
        state.update_context(message)
        # state = await hooks.llm_stream_after(state)

        # 如果中途出现大模型的认证失败等网络级阻断
        if getattr(message, "stop_reason", "") in {"error", "aborted"}:
            state.error = getattr(message, "error_message", "Unknown error.")
            emitter.emit(TurnEndEvent(parent_event = turn_event))
            break

        # 3. 钩子窃听：如果有工具请求，立即阻塞本协程，跑到沙盒去执行然后组装出合规结果
        tool_results = await execute_tool_calls(message, state, emitter, hooks, turn_event)

        # 本地工具由于执行完毕拿到了结果反馈，写入 context 作为 LLM 继续往下猜的前提
        for res in tool_results:
            state.update_context(res)

        # 4. 压缩防止 context 超出模型窗口
        usage = getattr(message, "usage", None)
        total_tokens = getattr(usage, "total_tokens", 0) or 0
        compress_tokens = getattr(state.model, "compress_tokens", None)

        if compress_tokens is not None and total_tokens > compress_tokens:
            state = await hooks.compress_before(state)
            await compress_messages(state, emitter, turn_event)
            state = await hooks.compress_after(state)

        emitter.emit(TurnEndEvent(parent_event = parent_event))

        # 5. 判断本局是否终了
        if not tool_results or await hooks.loop_break(state):
            break

        # 6. 防爆走阀门限制
        if state.cur_turn >= state.max_auto_turn:
            state.error = "Max auto turns capacity reached limit 15, forced shutdown to avoid loops."
            break

    return message
