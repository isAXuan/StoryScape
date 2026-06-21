"""Uniaix 专用 Chat Completions 协议提供商适配器实现。

基于 OpenAI 旧版通用 Chat Completions 协议，针对 Uniaix 进行定制：
- 添加 Uniaix 必需的 HTTP Referrer 和 X-Title headers
- 使用 Uniaix 特有的路由选项
- 适配 Uniaix 的响应格式
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
import inspect
from typing import Any, Literal, cast
from pydantic import BaseModel
from loguru import logger
from json_repair import repair_json, loads


from .._utils.env_api_keys import get_env_api_key
# from .._utils.transform_messages import transformed_context
from .._utils.sanitize_unicode import sanitize_surrogates

from ..types._stream import AssistantMessageEventStream
from ..types.message import (
    Message,
    UserMessage,
    AssistantMessage,
    ToolResultMessage,
    Context,
    TextContent,
    ThinkingContent,
    Usage,  
    ToolCall
)
from ..types._event import (
    ThinkingDeltaEvent,
    ToolCallDeltaEvent,
    DoneEvent,
    ErrorEvent,
    StartEvent,
    TextDeltaEvent,
)
from ..types.options import ModelOptions, StreamOptions
from ..types.model import Model


def transformed_context(
    context: Context,
) -> Context:
    transformed = []
    messages = context.messages
    n = len(messages)
    
    i = 0  # 主指针：当前正在处理的消息位置
    
    while i < n:
        msg = messages[i]

        # 1. UserMessage: 直接透传
        if msg.role == "user":
            transformed.append(msg)
            i += 1
            continue

        # 2. AssistantMessage
        # list[TextContent | ThinkingContent | ToolCall]
        if msg.role == "assistant":
            # 提取所有 ToolCall 区块
            tool_calls = [block for block in msg.content if isinstance(block, ToolCall)]
            
            # 没有工具调用，正常透传
            if not tool_calls:
                transformed.append(msg)
                i += 1
                continue
                
            # --- 核心：基于确定性业务约束的“切片探测法” ---
            k = len(tool_calls)
            
            # 向后安全探测，最多抓取 k 个元素，且必须是 ToolResultMessage
            # 这样做可以避免吃掉后面的非 Tool 消息（虽然按业务逻辑说不存在，但加上类型判断更严谨）
            actual_tool_res = []
            for x in range(i + 1, min(i + 1 + k, n)):
                if isinstance(messages[x], ToolResultMessage):
                    actual_tool_res.append(messages[x])
                else:
                    break

            if len(actual_tool_res) == k:
                # 完美闭环：保留 Assistant 并加入所有 Tool 结果
                transformed.append(msg)
                transformed.extend(actual_tool_res)
            else:
                # 将实际已经返回的结果提取为字典，方便按 id 匹配
                res_map = {res.tool_call_id: res for res in actual_tool_res}
                
                transformed_tool_res = []
                # 严格按照发起的 tool_calls 顺序，逐个核对和补全
                for tc in tool_calls:
                    # 获取 tool_call 的 id 和 name (请根据你的 ToolCall 实际属性名调整，这里假设是 id 和 name)
                    tc_id = getattr(tc, "id", "")
                    tc_name = getattr(tc, "name", "")
                    
                    if tc_id in res_map:
                        # 找到了真实执行结果，直接加入
                        transformed_tool_res.append(res_map[tc_id])
                    else:
                        # 没有找到对应结果，构造一个报错/中断的占位结果
                        # 假设你有 TextContent 类，请根据实际构造函数调整参数
                        error_text = TextContent(text="System error: The tool execution was interrupted and did not complete.")
                        mock_res = ToolResultMessage(
                            tool_call_id=tc_id,
                            tool_name=tc_name,
                            content=[error_text]
                        )
                        transformed_tool_res.append(mock_res)
                
                # 保留完整的 Assistant，并加入补全后的所有结果
                transformed.append(msg)
                transformed.extend(transformed_tool_res)
            
            # 重要：无论是否补全，指针只需要跨过 Assistant(1步) + 真实扫到的结果数(len(actual_res))
            # 那些伪造出来的结果不需要跨过去，因为它们根本不在原数组里
            i += 1 + len(actual_tool_res)
            continue

    return Context(
        system=context.system,
        tools=context.tools,
        messages=transformed,
    )


def _obj_get(obj: object, key: str, default: object = None) -> object:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _map_stop_reason(
    reason: object,
) -> Literal["stop", "length", "toolUse", "error", "aborted"]:
    if not isinstance(reason, str):
        return "stop"
    normalized = reason.lower()
    if normalized in {"length", "max_tokens", "maxlength"}:
        return "length"
    if normalized in {"tool_calls", "tool_call", "function_call"}:
        return "toolUse"
    return "stop"

def help_show_stream_return_order(model_class):
    annotations = model_class.__annotations__
    
    def process_field_type(field_type):
        # 如果字段是 Pydantic 模型类型
        if isinstance(field_type, type) and issubclass(field_type, BaseModel):
            return help_show_stream_return_order(field_type)  # 递归处理
        elif hasattr(field_type, '__origin__') and field_type.__origin__ == list:
            # 如果字段是 List 类型，递归处理 List 中的元素类型
            return [process_field_type(field_type.__args__[0])]
        elif hasattr(field_type, '__origin__') and field_type.__origin__ == dict:
            # 如果字段是 Dict 类型，递归处理 Dict 的键和值类型
            return {
                "key": process_field_type(field_type.__args__[0]),
                "value": process_field_type(field_type.__args__[1])
            }
        else:
            return str(field_type)  # 普通类型字段

    # 递归处理每个字段的类型
    result = {field: process_field_type(field_type) for field, field_type in annotations.items()}
    return result

def merge_reasoning_details(list_a, list_b):
    merged_map = {}
    
    for item in (list_a or []) + (list_b or []):
        item_type = item.get('type')
        
        if item_type in merged_map:
            field_key = item_type.split('.')[-1] 
            if field_key in item:
                merged_map[item_type][field_key] += item[field_key]
        else:
            merged_map[item_type] = {k: v for k, v in item.items()}
            
    result = []
    for new_index, merged_item in enumerate(merged_map.values()):
        merged_item['index'] = new_index
        result.append(merged_item)
        
    return result

    
def _build_params(
    model: Model,
    context: Context,
    model_options: ModelOptions,
    params_rules: list[str],
) -> dict[str, Any]:
    # 1. messages
    messages: list[dict[str, object]] = []
    # 1.1 系统提示
    if context.system:
        messages.append(
            {"role": "system", "content": sanitize_surrogates(context.system)}
        )

    # 1.2 消息内容
    for message in context.messages:
        # UserMessage：str | list[TextContent | ImagesContent]
        if message.role == "user":
            if isinstance(message.content, str):
                # 纯文本情况
                messages.append({"role": "user", "content": sanitize_surrogates(message.content)})
            elif isinstance(message.content, list):
                # 多模态（图文、多图）情况
                parts: list[dict[str, object]] = []
                for item in message.content:
                    if item.type == "text":
                        parts.append({
                            "type": "text",
                            "text": sanitize_surrogates(item.text)
                        })
                    elif item.type == "image":
                        for img_data in item.data:
                            url = img_data if item.source == "url" else f"data:{item.mime_type};base64,{img_data}"
                            parts.append({
                                "type": "image_url",
                                "image_url": {"url": url}
                            })
                    elif item.type == "video":
                        for vid_data in item.data:
                            url = vid_data if item.source == "url" else f"data:{item.mime_type};base64,{vid_data}"
                            parts.append({
                                "type": "video_url",
                                "video_url": {"url": url}
                            })

                messages.append({"role": "user", "content": parts})
            continue

        # AssistantMessage：list[TextContent | ThinkingContent | ToolCall]
        if message.role == "assistant":
            assistant_message: dict[str, object] = {
                "role": "assistant",
                "content": None,
            }

            tool_call_blocks = [
                block for block in message.content if block.type == "toolCall"
            ]
            if tool_call_blocks:
                assistant_message["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False),
                        },
                    }
                    for call in tool_call_blocks
                ]

            text_blocks = [
                sanitize_surrogates(block.text)
                for block in message.content
                if block.type == "text" and block.text.strip()
            ]
            if text_blocks:
                assistant_message["content"] = "".join(text_blocks)

            # 处理 reasoning_details
            if message.reasoning_details:
                # print("load reasoning_details")
                assistant_message["reasoning_details"] = message.reasoning_details

            messages.append(assistant_message)
            continue

        # ToolResultMessage：list[TextContent | ImagesContent]
        if message.role == "toolResult":
            # 采用多模态列表结构
            tool_content: list[dict[str, object]] = []

            for item in message.content:
                if item.type == "text":
                    tool_content.append({
                        "type": "text",
                        "text": sanitize_surrogates(item.text)
                    })
                elif item.type == "image":
                    # 保持与 user 逻辑一致的图片处理
                    for img_data in item.data:
                        url = img_data if item.source == "url" else f"data:{item.mime_type};base64,{img_data}"
                        tool_content.append({
                            "type": "image_url",
                            "image_url": {"url": url}
                        })

            # 构建基础消息对象
            tool_message: dict[str, object] = {
                "role": "tool",
                "tool_call_id": message.tool_call_id,
                "content": tool_content if tool_content else "",
                "name": message.tool_name
            }

            messages.append(tool_message)


    # 2. 构建 payload
    payload: dict[str, object] = {
        "model": model.id,
        "messages": messages,
        "stream": True,
    }
    # 3. tools
    if context.tools:
        tools: list[dict[str, object]] = []
        for tool in context.tools:
            function: dict[str, object] = {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            tools.append(
                {
                    "type": "function",
                    "function": function,
                }
            )
        payload["tools"] = tools

    # 3b. model_options 参数（AI 载荷层）xs
    payload.update(model_options.to_payload(params_rules))

    return payload


async def _resolve_payload_hook(
    stream_options: StreamOptions, payload: dict[str, Any]
) -> dict[str, Any]:
    """执行针对提供商原生载荷在发送前实施异步拦截或者动态覆写的逃生口回调机制。"""
    if stream_options.hook is None:
        return payload
    maybe = stream_options.hook(payload)
    if asyncio.iscoroutine(maybe):
        updated = await maybe
    else:
        updated = maybe
    if isinstance(updated, dict):
        return cast(dict[str, object], updated)
    return payload


def stream_uniaix_completions(
    model: Model,
    context: Context,
    stream_options: StreamOptions,
    model_options: ModelOptions | None = None,
) -> AssistantMessageEventStream:
    """全面接管并控制 Uniaix 的 completions 请求，封装并向外围丢出多端统一时序流管实例。"""
    stream = AssistantMessageEventStream()

    async def runner() -> None:
        output = AssistantMessage(
            content=[],
            api=model.api,
            provider=model.provider,
            model=model.id,
        )
        try:
            # logger.debug(f"openrouter_opts is:\n {stream_options}\n model_options is:\n{model_options}")

            api_key = stream_options.api_key or get_env_api_key(model.provider)
            if not api_key:
                raise ValueError(f"No API key for provider: {model.provider}")

            try:
                from openai import AsyncOpenAI
                from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
            except ImportError as exc:
                raise RuntimeError(
                    "openai package is required. Run: uv sync --extra providers"
                ) from exc

            import httpx
            _timeout = stream_options.timeout if stream_options.timeout is not None else httpx.Timeout(None, connect=30.0)
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=stream_options.base_url,
                timeout=_timeout,
            )

            normalized_context = transformed_context(context)
            params_rules = [param.name for param in inspect.signature(client.chat.completions.create).parameters.values()]
            payload = _build_params(model, normalized_context, model_options, params_rules)
            payload = await _resolve_payload_hook(stream_options, payload)
            # print(stream_options)
            openai_stream = await client.chat.completions.create(**payload)
            stream.push(StartEvent(message=output))
            await asyncio.sleep(0)

            current_block: TextContent | ThinkingContent | ToolCall | None = None
            tool_blocks: dict[int, ToolCall] = {}
            tool_partial_args: dict[int, str] = {}

            # 打印 ChatCompletionChunk 的字段顺序, 希望帮助理解模型返回的字段顺序
            # print(json.dumps(help_show_stream_return_order(ChatCompletionChunk), ensure_ascii=False, indent=2))
            reasoning_details = None
            async for chunk in openai_stream:
                # 接受顺序：
                # 1. reasoning([reasoning_delta + reasoning_details_encrypted] * n + [reasoning_details])
                # 2. text/tool_call
                # 3. finish_reason
                # 4. usage
                # print(chunk)
                choices = _obj_get(chunk, "choices", None)
                choice = choices[0] if isinstance(choices, list) and choices else None
                if choice is None:
                    continue

                usage = _obj_get(chunk, "usage", None)
                if usage is not None:
                    output.usage = Usage(**usage.model_dump())

                finish_reason = _obj_get(choice, "finish_reason", None)
                if finish_reason is not None:
                    output.stop_reason = _map_stop_reason(finish_reason)

                delta = _obj_get(choice, "delta", None)
                if delta is None:
                    continue

                # 处理 reasoning
                # [reasoning_delta + reasoning_details] * n
                reasoning_delta = _obj_get(delta, "reasoning", None)
                if reasoning_delta: 
                    if current_block is None or current_block.type != "thinking":
                        current_block = ThinkingContent(thinking="")
                        output.content.append(current_block)

                    current_block.thinking += reasoning_delta
                    output.reasoning_details = merge_reasoning_details(output.reasoning_details, _obj_get(delta, "reasoning_details", None))
                    stream.push(ThinkingDeltaEvent(contentIndex=len(output.content) - 1, delta=reasoning_delta, message=output))
                    await asyncio.sleep(0)
                    continue
                
                # [reasoning_details_encrypted]
                reasoning_details = _obj_get(delta, "reasoning_details", None)
                if reasoning_details:
                    output.reasoning_details = merge_reasoning_details(output.reasoning_details, reasoning_details)
                    continue

                # 处理 text
                text_delta = _obj_get(delta, "content", None)
                if text_delta:
                    # 新的开始，或者 从 reasoning 转换到 text
                    if current_block is None or current_block.type != "text":
                        current_block = TextContent(text="")
                        output.content.append(current_block)

                    current_block.text += text_delta
                    stream.push(TextDeltaEvent(contentIndex=len(output.content) - 1, delta=text_delta, message=output))
                    await asyncio.sleep(0)
                    continue

                # 处理 tool_call
                delta_tool_calls = _obj_get(delta, "tool_calls", None)
                if isinstance(delta_tool_calls, list):
                    for delta_call in delta_tool_calls:
                        # 处理 function_call
                        index = _obj_get(delta_call, "index")
                        function = _obj_get(delta_call, "function", None)
                        # print("xxxxxxxxxxxxx", _obj_get(function, "name", ""))
                        existing_call = tool_blocks.get(index)
                        if function and existing_call is None:
                            new_call = ToolCall(
                                id=str(_obj_get(delta_call, "id", "")),
                                name=str(_obj_get(function, "name", "")),
                                arguments={},
                            )
                            output.content.append(new_call)
                            tool_blocks[index] = new_call
                            tool_partial_args[index] = ""
                            existing_call = new_call

                        args_delta = _obj_get(function, "arguments", None)
                        if args_delta:
                            tool_partial_args[index] = tool_partial_args.get(index, "") + args_delta
                            existing_call.arguments = loads(repair_json(tool_partial_args[index]))
                            content_index = output.content.index(existing_call)
                            stream.push(ToolCallDeltaEvent(contentIndex=content_index, delta=f"{existing_call.name}: {args_delta}", message=output))
                            await asyncio.sleep(0)

            # if any(block.type == "toolCall" for block in output.content):
            #     output.stop_reason = "toolUse"

            if output.stop_reason in {"error", "aborted"}:
                raise RuntimeError("An unknown error occurred")

            stream.push(DoneEvent(reason=cast(Literal["stop", "length", "toolUse"], output.stop_reason), message=output))
            await asyncio.sleep(0)
            stream.set_result(output)
            stream.end(output)
        except Exception as exc:
            import traceback
            from openai import APIError
            full_traceback = traceback.format_exc()
            if isinstance(exc, APIError) and exc.body:
                full_traceback = f"{full_traceback}\nAPI Error Body: {exc.body}"
            output.stop_reason = (
                "aborted" if str(exc).lower().find("abort") >= 0 else "error"
            )
            output.error_message = full_traceback
            stream.push(ErrorEvent(reason=output.stop_reason, message=output))
            await asyncio.sleep(0)
            stream.set_result(output)
            stream.end(output)

    asyncio.create_task(runner())
    return stream
