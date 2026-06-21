# pi_agent
One Agent query, including

```bash 
run sequence：
1. agent_start (tip)
2. user_update from start input
# hook.loop_before
LOOP:
# hook.turn_start_before
3. turn_start (tip)
# hook.turn_start_after
# hook.user_update_before
# 4. user_update from queue (maybe)
# hook.user_update_after
# hook.llm_stream_before
5. llm_stream (pi_ai.types._event: AssistantMessageEvent)
    5.1 aborted
    5.2 start
    5.3 thinking_delta
    5.4 text_delta/tool_call_delta
    5.5 done/error
    5.6 AssistantMessageEvent 之外 的 pi_ai 事件（暂时不会，因为一般同步更改）
# hook.llm_stream_after
# hook.tool_calls_before
6. tool_calls
    6.1 多少个工具执行
    6.2 tool_execution_start
    6.3 tool_execution_end
# hook.tool_calls_after
# hook.compress_before
7. compress_messages
    7.1 compress_start
    7.2 stream_assistant_response ...
    7.3 compress_end
# hook.compress_after
# hook.turn_end_before
8. turn_end (tip)
# hook.turn_end_after
9. agent_end (tip)
```


pi_agent 有四层架构

- `_engine/`: agent的引擎架构，整个`loop_react` + `hook` + `compressor`
- `_api_containers_sops/`: Provider adapters params (OpenRouter, etc.) implementing `stream()` or `complete()`
- `types/`: 所有的类型定义。主要关注的有 message  + event + model + options. `model只是模型的静态能力说明，options是才是参数层 = model参数+stream参数`
- `agent.py`:  `query()` 访问一次agent的入口函数

## Running Tests

```bash
python quick_pi_agent.py          # pi_agent demo (stream/complete API)
```