"""发往 seed_ai 大模型的桥接降维转换与流式拦截获取。"""
import copy
from seed_ai import stream, AssistantMessage

from ..types.message import AgentContext
from ..types.state import AgentState
from ..types.events import EventEmitter, AbortEvent, ErrorEvent, BaseEvent

def build_ai_context(agent_ctx: AgentContext) -> AgentContext:
    """提取可以发送给 seed_ai 的上下文，执行安全降维，过滤掉底盘不认识的自定义消息。"""
    return agent_ctx

async def llm_stream(
    state: AgentState,
    emitter: EventEmitter,
    parent_event: BaseEvent
) -> AssistantMessage:
    """发起网络请求，发射流式事件给打字机，并返回整理重组完成的最终 AssistantMessage。"""

    # 将 Agent 的宽泛结构提纯为底层网络发送格式
    ai_context = build_ai_context(state.context)

    # 调起底座流
    response_stream = stream(
        model=state.model,
        context=ai_context,
        stream_options=state.stream_options,
        model_options=state.model_options,
    )
    last_message = None
    try:
        async for event in response_stream:
            # 1. 记录最近的消息残片，用于中断时返回
            if hasattr(event, 'message'):
                last_message = event.message

            # 2. 检查外部中断信号
            if state.is_aborted:
                # 构造中断消息
                abort_msg = copy.copy(last_message) if last_message else AssistantMessage()
                abort_msg.stop_reason = "aborted"

                emitter.emit(AbortEvent(parent_event = parent_event))

                # 重要：主动调用 fail 或 end 以释放 response_stream 内部的 Future
                # 这样可以防止其他地方 await result() 时死锁
                response_stream.end(abort_msg)
                return abort_msg

            event.parent_event = parent_event
            emitter.emit(event)
            
        # 4. 迭代正常结束（收到 _EOS 哨兵），获取最终聚合结果
        return await response_stream.result()

    except Exception as e:
        # 确保异常能传播到流的状态中
        response_stream.fail(e)
        print(e)
        emitter.emit(ErrorEvent(parent_event = parent_event))
        raise
