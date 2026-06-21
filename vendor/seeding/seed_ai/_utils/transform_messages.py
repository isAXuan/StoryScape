"""跨提供商模型消息统一垫片转换机制。

该抽象模块专门对应及移植自 TS 的 `transform-messages.ts`。
主要用于当用户在多次追问会话中来回切换了处于不同后台甚至不同云厂家的底座架构时，对历史消息上下文做兼容性静默重整与安全转换映射：
1) 思考内容块 (Thinking) 降级/阻断/剥离再保留；
2) 格式混乱异常的工具调用编号 (Tool Call ID) 归一化派生挂载映射；
3) 针对会话末尾若异常截断缺失工具执行结果 (Tool Result) 时强行阻绝拦截、闭环并补合成合法的伪错误返回信息以防服务挂起或幻视。

典型使用场景：
- 多模型串联：同一个对话中先用 Claude 生成，再切到 GPT-4o 再切回来
- Provider 切换：从 OpenAI API 切换到 Azure OpenAI 或 OpenRouter
- 工具调用链中断：Assistant 发起了 tool_call 但用户/系统没有返回 tool_result 就继续发下一条消息
"""

from __future__ import annotations

import time
from collections.abc import Callable

from ..types.model import Model
from ..types.message import (
    AssistantMessage,
    Context,
    Message,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
)

NormalizeToolCallId = Callable[[str, Model, AssistantMessage], str]


def transform_messages(
    messages: list[Message],
    model: Model,
    normalize_tool_call_id: NormalizeToolCallId | None = None,
) -> list[Message]:
    """将被截获的用户及过往助手等历史消息列表集合转化为当下挂在当前指定目标模型时，其底层原配器可以安全接受消费的安全标准形态度。

    关键规避策略点：
    - 当检查出上下文跨模型流转切换时，将竭力剔除过滤掉目标下级模型可能会拒绝接受抛错的冗余细枝末节（如夹带部分专属模型私有格式的思考加密签名字段 thought signature 等）。
    - 全局追踪记录当前整个会话流中的 tool call id 原型与目标生成归一化处理映射字典键值，确保本轮后续发出的 toolResult 可以不掉链子被正确关联消费认领。

    Args:
        messages: 历史消息列表，可能是多模型混合的上下文
        model: 当前目标模型，用于判断是否跨模型需要转换
        normalize_tool_call_id: 可选回调，将 provider A 的 tool_call_id 格式转换为 provider B 的格式
    """
    # tool_call_id_map: 记录 tool_call_id 从原格式到归一化格式的映射
    # key=原始ID（如 Anthropic 生成的 "toolu_01HXABC123xyz"）
    # value=归一化ID（如 OpenAI 能接受的 "anth_tc_0"）
    # 在 tool_result 到达时需要逆向查找，将新ID映射回旧ID
    tool_call_id_map: dict[str, str] = {}

    transformed: list[Message] = []
    # ========== 第一遍：逐消息逐块转换，建立 tool_call_id_map ==========
    # 遍历每条消息，根据目标模型做必要的转换
    for msg in messages:
        # UserMessage：无需转换，直接透传
        if msg.role == "user":
            transformed.append(msg)
            continue

        # ToolResultMessage：需要做 tool_call_id 的逆向映射
        # 此时 tool_call_id_map 中已记录了 assistant 发起的 tool_call 的旧ID→新ID映射
        # tool_result 到达时，用新ID去 map 里查，如果匹配说明是归一化过的，需要还原为原始ID
        if msg.role == "toolResult":
            normalized_id = tool_call_id_map.get(msg.tool_call_id)
            if normalized_id and normalized_id != msg.tool_call_id:
                # 命中映射表，说明这个 tool_result 对应的 assistant 消息经过了 ID 归一化
                # 需要把新ID替换回原始ID，确保与最初的 tool_call 保持一致
                transformed.append(
                    ToolResultMessage(
                        tool_call_id=normalized_id,
                        tool_name=msg.tool_name,
                        content=msg.content,
                        details=msg.details,
                        is_error=msg.is_error,
                        timestamp=msg.timestamp,
                    )
                )
            else:
                transformed.append(msg)
            continue

        # 判断这条 assistant 消息是否是目标模型生成的
        # 如果 provider/api/model 任一不同，说明是跨模型场景，需要做转换
        is_same_model = (
            msg.provider == model.provider
            and msg.api == model.api
            and msg.model == model.id
        )

        new_content: list[TextContent | ThinkingContent | ToolCall] = []
        # ========== 逐块处理 content ==========
        for block in msg.content:
            # --- ThinkingContent 处理 ---
            # 不同 provider 的 thinking 格式不兼容，切换时需要降级或丢弃
            if block.type == "thinking":
                # redacted=True 表示思考内容被平台安全过滤器脱敏/隐藏
                # 只有同模型才能继续保留原始格式，跨模型直接丢弃（因为 signature 已无效）
                if block.redacted:
                    if is_same_model:
                        new_content.append(block)
                    continue
                # 有 thinking_signature 表示提供商私有格式，跨模型不能传递
                if is_same_model and block.thinking_signature:
                    new_content.append(block)
                    continue
                # 空思考内容直接跳过
                if block.thinking.strip() == "":
                    continue
                # 同模型：保留原始 thinking 内容块
                if is_same_model:
                    new_content.append(block)
                else:
                    # 跨模型：thinking 无法被目标模型理解，降级为普通文本
                    new_content.append(TextContent(text=block.thinking))
                continue

            # --- TextContent 处理 ---
            # 文本块是通用的，直接复制（保留 text_signature 供多轮上下文复用）
            if block.type == "text":
                new_content.append(
                    TextContent(text=block.text, text_signature=block.text_signature)
                )
                continue

            # --- ToolCall 处理 ---
            # 工具调用涉及 ID 格式兼容性问题，跨模型需要归一化
            normalized = ToolCall(
                id=block.id,
                name=block.name,
                arguments=dict(block.arguments),
                thought_signature=block.thought_signature,
            )

            # thought_signature 是 provider 私有字段，跨模型必须清除
            if (not is_same_model) and normalized.thought_signature is not None:
                normalized.thought_signature = None

            # 跨模型时，使用回调函数将 tool_call_id 转换为目标 provider 能接受的格式
            # 同时记录旧ID→新ID 映射，供后续 tool_result 逆向查找
            if (not is_same_model) and normalize_tool_call_id is not None:
                normalized_id = normalize_tool_call_id(block.id, model, msg)
                if normalized_id != block.id:
                    tool_call_id_map[block.id] = normalized_id
                    normalized.id = normalized_id

            new_content.append(normalized)

        # 重建 AssistantMessage，保留原始元信息（api/provider/model/usage 等不变）
        transformed.append(
            AssistantMessage(
                content=new_content,
                api=msg.api,
                provider=msg.provider,
                model=msg.model,
                usage=msg.usage,
                stop_reason=msg.stop_reason,
                error_message=msg.error_message,
                timestamp=msg.timestamp,
            )
        )

    # ========== 第二遍：检测并补全缺失的 Tool Result ==========
    # 防止 assistant 发起了 tool_call 但中途对话中断（用户没返回 tool_result）导致模型挂起
    #
    # 状态机：
    # - pending_tool_calls: 当前待回复的 tool_call 队列（遇到 assistant 时更新）
    # - existing_tool_result_ids: 已收到回复的 tool_call ID 集合（遇到 tool_result 时添加）
    result: list[Message] = []
    pending_tool_calls: list[ToolCall] = []
    existing_tool_result_ids: set[str] = set()

    def _append_missing_tool_results() -> None:
        """将 pending_tool_calls 中没有对应 tool_result 的调用补全为错误结果。

        这处理的是对话异常中断场景：assistant 说"我来查一下天气"然后发起了 tool_call，
        但用户没返回 tool_result 就发了新消息或结束了对话。此时需要注入一条错误结果
        告知模型"这个工具调用没有返回"，防止模型一直等待。
        """
        nonlocal pending_tool_calls
        nonlocal existing_tool_result_ids
        if not pending_tool_calls:
            return

        for tool_call in pending_tool_calls:
            if tool_call.id in existing_tool_result_ids:
                continue  # 已有对应结果，跳过
            # 注入伪结果：is_error=True 表示工具执行失败
            result.append(
                ToolResultMessage(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    content=[TextContent(text="No result provided")],
                    is_error=True,
                )
            )

        # 重置状态
        pending_tool_calls = []
        existing_tool_result_ids = set()

    for msg in transformed:
        if msg.role == "assistant":
            # 遇到新的 assistant 消息，先检查上一次 pending 的 tool_calls 是否有缺失结果
            # （说明上一次 assistant 发起的工具调用没有被正常回复）
            _append_missing_tool_results()

            # 错误/aborted 状态的 assistant 消息不包含有效 tool_call，跳过
            if msg.stop_reason in {"error", "aborted"}:
                continue

            # 提取这条 assistant 消息中的所有 tool_calls，更新待回复队列
            assistant_tool_calls = [b for b in msg.content if b.type == "toolCall"]
            if assistant_tool_calls:
                pending_tool_calls = [
                    ToolCall(id=b.id, name=b.name, arguments=b.arguments)
                    for b in assistant_tool_calls
                ]
                existing_tool_result_ids = set()  # 新的一批，清空旧的
            result.append(msg)
            continue

        if msg.role == "toolResult":
            # 记录这条 tool_result 对应的 tool_call_id
            existing_tool_result_ids.add(msg.tool_call_id)
            result.append(msg)
            continue

        if msg.role == "user":
            # 用户发了新消息，但 pending 的 tool_calls 还没有全部收到结果
            # 说明用户没有按顺序回复就发了新消息，补全缺失结果后继续
            _append_missing_tool_results()

        result.append(msg)

    return result


def transformed_context(
    context: Context,
    model: Model,
    normalize_tool_call_id: NormalizeToolCallId | None = None,
) -> Context:
    """包装辅助函数：用于在整体全维度 Context 级别触发级联实施安全的 `transform_messages` 脱敏映射转换逻辑。

    将 Context 中的 messages 列表经过 transform_messages 转换后，
    重新组装成一个新的 Context 返回。system 和 tools 不做转换直接透传。

    Args:
        context: 原始会话上下文（可能包含多模型混合的历史消息）
        model: 当前目标模型
        normalize_tool_call_id: tool_call_id 归一化回调函数

    Returns:
        Context: 转换后的新上下文，messages 已按目标模型适配
    """
    return Context(
        system=context.system,
        messages=transform_messages(context.messages, model, normalize_tool_call_id),
        tools=context.tools,
    )
