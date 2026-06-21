# pi_ai
One LLM query, supporting an API layer from multiple vendors (such as OpenRouter, etc.)

```bash 
stream sequence：
1. reasoning([reasoning_delta + reasoning_details_encrypted] * n + [reasoning_details])
2. text/tool_call/...
3. finish_reason
4. usage
```

pi_ai 有四层架构

- `_api_containers/`: Provider adapters (OpenRouter, etc.) implementing `stream()` or `complete()`
- `_api_containers_sops/`: Provider adapters params (OpenRouter, etc.) implementing `stream()` or `complete()`
- `types/`: 所有的类型定义。主要关注的有 message  + event + model + options. `model只是模型的静态能力说明，options是才是参数层 = model参数+stream参数`
- `stream.py`:  `stream()` and `complete()` 访问一次AI的入口函数

## Running Tests

```bash
python quick_pi_ai.py          # pi_ai demo (stream/complete API)
```

stream/complete 访问一次AI，都需要四个参数
    - model: Model,
    - context: Context,
    - stream_options: StreamOptions,
    - model_options: ModelOptions | None = None,