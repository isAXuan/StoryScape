import asyncio
import json
import os
from pydantic import BaseModel, Field, ConfigDict
from pydantic.dataclasses import dataclass as pydantic_dataclass
from dotenv import load_dotenv
import sys
print("当前使用的 Python 路径：", sys.executable)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(".env")

from seed_ai import stream, complete
from seed_ai.types import Context, ThinkingDeltaEvent, UserMessage, StreamOptions, ModelOptions, Model, ModelCost
from seed_ai import OpenRouterCompletionsStreamOptions, UniaixCompletionsStreamOptions
from seed_ai.types.message import ImagesContent, TextContent, Tool
from seed_ai.types._event import TextDeltaEvent, DoneEvent

# API Key 从环境变量加载
API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
print("API_KEY:", API_KEY)
base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
test_url = "https://vod.pipi.cn/27df3294vodbj1251246104/f508b89e5145403720009859470/f0.png"

class EchoTool(Tool):
    name: str = "echo"
    label: str = "Echo"
    description: str = "Echo back the provided text"
    parameters: dict[str, object] = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "value": {"type": "string", "description": "Text to echo"}
        },
        "required": ["value"],
    })

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, object],
        signal: object | None = None,
        on_update=None,
    ) :
        _ = tool_call_id, signal
        if on_update is not None:
            on_update(
                {
                    "content": [{"type": "text", "text": "Echo tool is running..."}],
                    "details": {"stage": "running"},
                }
            )
        return {
            "content": [{"type": "text", "text": f"echoed: {params['value']}"}],
            "details": {"tool": "echo"},
        }


class Echo2Tool(EchoTool):
    name: str = "echo2"

async def run_ai():
    # model = get_model("free", "z-ai/glm-4.5-air:free")
    model = Model(
        # id="google/gemini-3.1-pro-preview",
        # id="anthropic/claude-opus-4.6",
        id="gpt-5.4",
        # id="z-ai/glm-5.1",
        name="GPT-5.4",
        api="openrouter-completions",
        provider="openrouter",
        support_reasoning=True,
        input=["text", "image"],
        cost=ModelCost(input=0.5, output=3.0, cacheRead=0.05, cacheWrite=0.08),
        context_window=1048576,
        max_tokens=65000,
    )

    def show_payload(payload: dict) -> dict:
        print("[payload]", json.dumps(
            payload,
            ensure_ascii=False, indent=2
        ))
        return payload

    # 测试：URL 模式图片 + complete()
    print("=== 图片 URL 模式测试（complete）===")
    result = await complete(
        model,
        Context(
            system="You are a concise assistant. ",
            messages=[
                UserMessage(content=[
                    # ImagesContent(source="url", data=[test_url]),
                    # TextContent(text="请描述这张图片的内容。"),
                    # TextContent(text="Use the echo tool and echo2 tool to repeat the text."),
                    TextContent(text="10*10+10."),
                ])
            ],
            tools=[EchoTool(), Echo2Tool()],
        ),
        StreamOptions(
            base_url=base_url,
            api_key=API_KEY,
            hook=show_payload,
        ),
        ModelOptions(
            api_options=UniaixCompletionsStreamOptions(reasoning_effort="medium"),
            tool_choice="auto"
        ),
    )
    if result.stop_reason == "error":
        print(result.error_message)
    else:
        for block in result.content:
            # if block.type == "error":
            #     print()
            if block.type == "thinking":
                print("thinking:", block.thinking, flush=True)
            if block.type == "text":
                print("text:", block.text, flush=True)
        print(f"[stop_reason={result.stop_reason}, error={result.error_message}, blocks={len(result.content)}]")

    # 测试：URL 模式图片 + stream()
    print("\n=== 图片 URL 模式测试（stream）===")
    # return
    event_stream = stream(
        model,
        Context(
            system="You are a concise assistant. ",
            messages=[
                UserMessage(content=[
                    # ImagesContent(source="url", data=[test_url]),
                    # TextContent(text="请描述这张图片的内容。"),
                    # TextContent(text="Use the echo tool and echo2 tool to repeat the text."),
                    TextContent(text="1，2，4，6，8，9，3的平均值是多少岁？"),
                ])
            ],
            tools=[EchoTool(), Echo2Tool()],
        ),
        StreamOptions(
            base_url=base_url,
            api_key=API_KEY,
            # hook=show_payload,
        ), 
        ModelOptions(
            api_options=UniaixCompletionsStreamOptions(reasoning_effort="medium"),
            tool_choice="auto"
        ),
    )
    async for event in event_stream:
        # print(event)
        
        if event.type == "error":
            print(event.message)
            continue
        if isinstance(event, ThinkingDeltaEvent):   
            print(event.delta, end="", flush=True)  

        if isinstance(event, TextDeltaEvent):   
            print(event.delta, end="", flush=True)  
        
        # if isinstance(event, DoneEvent):
        #     print(event.message.usage.cost.total)
    print()


if __name__ == "__main__":
    asyncio.run(run_ai())
