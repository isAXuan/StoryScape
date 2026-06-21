"""seed_agent 内部定制的消息载体与时间轴对象拓展。"""

from __future__ import annotations

from pydantic import BaseModel, Field, TypeAdapter
from typing import Any, TypeAlias
from typing import Literal
from seed_ai import Context, Message, UserMessage

from .tool import AgentTool

class CompressorMessage(UserMessage):
    """不发送给大模型，仅留存在本地 Timeline (时间轴) 供 UI 进度追踪的内部标记。"""
    alias: Literal["compressor"] = "compressor"

    def pretty_line(self) -> str:
        return f"[CompressorMessage] timestamp={self.timestamp}"



# 广义聚合后的 Agent 通讯数据包规范，其向下兼容了原始所有 Message 类型。
AgentMessage: TypeAlias = Message | CompressorMessage | dict[str, Any]
agent_message_adapter = TypeAdapter(AgentMessage)


class AgentSystem(BaseModel):
    """复合的智能体系统人格对象，相比简单的 str 更能控制多维度的结构注入。"""
    persona: str = ""
    instructions: str = ""
    rules: list[str] = Field(default_factory=list)

    def __str__(self) -> str:
        rules_str = "\n".join(f"- {r}" for r in self.rules) if self.rules else ""
        return f"{self.persona}\n\n{self.instructions}\n\n{rules_str}".strip()

class AgentContext(Context):
    """【滑动窗口】：供大模型推理使用的活跃语境通信帧 (可以被修整、摘要以适应 Token 上限)"""
    system: str | None = None
    messages: list[AgentMessage] = Field(default_factory=list)
    tools: list[AgentTool] | None = None

