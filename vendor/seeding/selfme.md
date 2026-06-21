# PiAgentX

## pi_ai
- py_ai 始终记住输出token是文字
    1. Start
    2. thinking_start
    3. thinking_delta
    4. thinking_end
    5. text_start
    6. text_delta
    7. text_end
    8. toolcall_start
    9. toolcall_delta
    10. toolcall_end
    11. done
    12. error
- 一次py_ai的调用可以包含的内容及顺序
    1. Context定义为单次模型生成调用的完整会话上下文记录 = `system: str | None + messages: list[Message] + tools: list[Tool]`
    2. 重点在messages是多个对象的集合体：
        - UserMessage（用户输入`str | list[TextContent | ImagesContent]`）
        - AssistantMessage（模型输出`list[TextContent | ThinkingContent | ToolCall]`）
        - ToolResultMessage（工具调用结果`list[TextContent | ImagesContent]`）
    3. 标准的流失消息输出顺序与格式：
        ```python
        from pi_ai._api_containers.openrouter_completions import help_show_stream_return_order
        from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

        print(json.dumps(help_show_stream_return_order(ChatCompletionChunk), ensure_ascii=False, indent=2))
        ```

