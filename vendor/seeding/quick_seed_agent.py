from __future__ import annotations

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field

from seed_agent import Agent, AgentState, AgentContext, AgentTool, tools
from seed_ai import (
    ToolResultMessage, 
    Model, StreamOptions, ModelOptions, OpenRouterCompletionsStreamOptions,
    ModelCost
)


"""Minimal seed_agent example — 演示 2×2 工具定义矩阵。

              │  params: BaseModel              │  a: int, b: int
  ────────────┼─────────────────────────────────┼──────────────────────────────
  class 协议  │  call 收 raw dict → params["v"] │  execute 自动拆包 → 具名 kwargs
  @tools 函数 │  call 收 model 实例 → params.v  │  call 收展开 kwargs → a, b
"""


# ─── Pydantic 参数模型 ─────────────────────────────────────────────────────

class EchoParameters(BaseModel):
    value: str = Field(..., description="Text to echo")


# ══════════════════════════════════════════════════════════════════════════════
# 模式一：class 协议 + params: BaseModel
# call 收到 raw dict，自行用 params["key"] 访问
# ══════════════════════════════════════════════════════════════════════════════

class EchoToolRaw(AgentTool):
    root_path: str = os.path.dirname(os.path.abspath(__file__))

    async def call(self, params: EchoParameters) -> str:
        """Echo back the provided text"""
        value = params["value"]   # params 是 raw dict
        print(f"\n[EchoToolRaw]: -> {value}  root={self.root_path}")
        return f"echoed: {value}"


# ══════════════════════════════════════════════════════════════════════════════
# 模式二：class 协议 + flat args
# execute 透过签名自动拆包 dict → kwargs，call 直接收到 a, b
# ══════════════════════════════════════════════════════════════════════════════

class AddToolRaw(AgentTool):
    async def call(self, a: int, b: int) -> str:
        """Add two numbers"""
        result = a + b   # a, b 已经是具名参数（execute 自动拆包）
        print(f"\n[AddToolRaw]: {a} + {b} = {result}")
        return f"{a} + {b} = {result}"


# ══════════════════════════════════════════════════════════════════════════════
# 模式三：@tools 函数 + params: BaseModel
# call 收到 EchoParameters model 实例，用 params.value 访问
# ══════════════════════════════════════════════════════════════════════════════

@tools
async def echo(params: EchoParameters) -> str:
    """Echo back the provided text"""
    print(f"\n[echo]: -> {params.value}")   # params 是 EchoParameters 实例
    return f"echoed: {params.value}"


# ══════════════════════════════════════════════════════════════════════════════
# 模式四：@tools 函数 + flat args
# call 收到展开的具名 kwargs
# ══════════════════════════════════════════════════════════════════════════════

@tools
async def add(a: int, b: int) -> str:
    """Add two numbers"""
    result = a + b   # a, b 直接是 int（@tools 自动拆包）
    # print(f"\n[add]: {a} + {b} = {result}")
    return f"{a} + {b} = {result}"


# ─── 独立测试（无需 Agent / 网络）─────────────────────────────────────────

async def test_tools_standalone():
    print("=" * 60)
    print("独立测试  2×2 矩阵")
    print("=" * 60)

    all_tools = [EchoToolRaw(), AddToolRaw(), echo, add]
    for t in all_tools:
        print(f"\n  [{type(t).__name__}]  name={t.name!r}")
        print(f"    description = {t.description!r}")
        print(f"    parameters  = {t.parameters}")
        assert t.name and t.description and t.parameters

    print()

    # 模式一：class + BaseModel — call 直接传 dict，用 params["key"]
    r = await EchoToolRaw().call({"value": "hello raw"})
    assert r == "echoed: hello raw", r
    print(f"① EchoToolRaw.call(raw dict): {r}")

    # 模式二：class + flat — execute 拆包（独立测试时直接传 kwargs）
    r = await AddToolRaw().call(a=3, b=7)
    assert r == "3 + 7 = 10", r
    print(f"② AddToolRaw.call(kwargs): {r}")

    # 模式二 execute 路径（引擎实际路径，自动拆包 dict）
    msg = await AddToolRaw().execute("id-add", {"a": 5, "b": 5}, None)
    assert msg.content[0].text == "5 + 5 = 10"
    print(f"② AddToolRaw.execute(dict→auto-unpack): {msg.content[0].text}")

    # 模式三：@tools + BaseModel — call 收到 model 实例
    r = await echo.call({"value": "hello typed"})
    assert r == "echoed: hello typed", r
    print(f"③ echo.call(dict→model): {r}")

    r = await echo.call(EchoParameters(value="direct model"))
    assert r == "echoed: direct model", r
    print(f"③ echo.call(model): {r}")

    # 模式四：@tools + flat — call 收到展开 kwargs
    r = await add.call({"a": 10, "b": 20})
    assert r == "10 + 20 = 30", r
    print(f"④ add.call(dict→kwargs): {r}")

    # execute 桥接
    msg = await echo.execute("id-001", {"value": "bridged"}, None)
    assert isinstance(msg, ToolResultMessage)
    assert msg.content[0].text == "echoed: bridged"
    print(f"\nexecute 桥接: {msg.content[0].text}")

    print("\n✅ 所有独立测试通过！")


# ─── Agent 集成测试 ────────────────────────────────────────────────────────

async def test_agent_integration():
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    model = Model(
        # id="openai/gpt-4o",
        id="google/gemini-3-flash-preview",
        name="GPT-4o Mini",
        api="openrouter-completions",
        provider="openrouter",
        support_reasoning=True,
        input=["text", "image"],
        cost=ModelCost(input=0.15, output=0.60, cacheRead=0.0, cacheWrite=0.0),
        context_window=1048576,
        max_tokens=16000,
    )

    context = AgentContext(
        system="You are a concise assistant. 最后是使用 echo 进行重复",
        tools=[echo, add]   # @tools 直接生成的 AgentTool 实例
    )
    stream_options = StreamOptions(
        api_key=api_key,
        base_url=base_url,
    )
    model_options = ModelOptions(
        api_options=OpenRouterCompletionsStreamOptions(reasoning={"effort": "medium"}),
    )

    print(f"\n[INFO] Creating new agent state")
    agent = Agent(initial_state=AgentState(
        work_root="./work",
        model=model,
        context=context,
        stream_options=stream_options,
        model_options=model_options,
    ))

    def get_type_chain(event) -> str:
        """
        迭代获取 event.type + parent_type 链条
        返回格式：type | parent1 | parent2 | ...
        """
        chain = []
        current = event

        # 循环收集所有 type，直到没有 parent 为止
        while current:
            # 拿到当前节点的 type，加入列表
            chain.append(f"{current.type}.{current.id}")
            
            # 取下一个 parent（如果没有就停止）
            current = getattr(current, "parent_event", None)  # 安全获取属性

        chain.reverse()
        # 用 | 连接
        return " | ".join(chain) + f" | message : {event.message.pretty_line()}" if hasattr(event, "message") else " | ".join(chain)

    def on_event(work_root, event) -> None:
        print(work_root, get_type_chain(event))

    unsubscribe = agent.subscribe()
    try:
        # await agent.query("Please use the echo tool to repeat: hello from seed-agent!")
        res = await agent.query("Please use the add tool to add 10 and 20.")
        print("finall res:\n", res)
        # from time import sleep
        # sleep(10)
    finally:
        f=1
        unsubscribe()

    # print("\n\n=== Final State Timeline ===")
    # for msg in agent.state.context.messages:
    #     role = getattr(msg, "role", "unknown")
    #     print(f"- [{role}]")
    #     if isinstance(msg, (UserMessage, AssistantMessage, ToolResultMessage)):
    #         for block in msg.content:
    #             if isinstance(block, TextContent):
    #                 print(f"  {block.text}")


async def main() -> None:
    await test_tools_standalone()

    print("\n" + "=" * 60)
    print("Agent 集成测试")
    print("=" * 60 + "\n")

    await test_agent_integration()


if __name__ == "__main__":
    asyncio.run(main())