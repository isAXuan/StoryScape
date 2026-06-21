"""处理大模型回调的 toolCall 并将其挂载到本地 AgentTool 上执行的行刑官沙盒。"""

from seed_ai import ToolResultMessage, TextContent, AssistantMessage

from ..types.state import AgentState
from ..types.hooks import AgentHooks
from ..types.events import (
    EventEmitter,
    ToolCallsStartEvent,
    ToolExecutionStartEvent,
    ToolExecutionEndEvent,
    ToolCallsEndEvent,
    BaseEvent
)

async def execute_tool_calls(
    message: AssistantMessage,
    state: AgentState,
    emitter: EventEmitter,
    hooks: AgentHooks,
    parent_event: BaseEvent
) -> list[ToolResultMessage]:
    """遍历 AssistantMessage 中的工具回调请求，拉起本地执行并等待结果返回。"""

    tool_calls = [content for content in message.content if getattr(content, "type", "") == "toolCall"]
    if not tool_calls:
        return []
        
    results: list[ToolResultMessage] = []
    available_tools = state.context.tools or []

    # 发送工具调用开始事件
    emitter.emit(ToolCallsStartEvent(parent_event = parent_event))

    for tool_call in tool_calls:
        if state.is_aborted:
            break

        # 寻找对应的工具映射
        target_tool = next((t for t in available_tools if t.name == tool_call.name), None)

        emitter.emit(ToolExecutionStartEvent(parent_event = parent_event))

        state.pending_tool_calls.add(tool_call.id)

        try:
            if not target_tool:
                raise ValueError(f"Tool {tool_call.name} not found in AgentContext.tools")

            # 使用状态大快照跑回调执行器
            result = await target_tool.execute(tool_call.id, tool_call.arguments, state.context)

        except Exception as exc:
            result = ToolResultMessage(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                content=[TextContent(text=f"Execution error: {exc}")],
                is_error=True,
            )

        state.pending_tool_calls.discard(tool_call.id)

        emitter.emit(ToolExecutionEndEvent(message = result, parent_event = parent_event))

        results.append(result)

    # 发送工具调用结束事件
    emitter.emit(ToolCallsEndEvent(parent_event = parent_event))

    return results
