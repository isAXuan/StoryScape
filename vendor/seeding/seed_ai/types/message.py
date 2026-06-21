from __future__ import annotations

from collections.abc import Mapping
from pydantic import BaseModel, Field, model_serializer
from datetime import datetime
from typing import Literal, Any
import uuid

from ._provider import Api, Provider
from .options import StopReason


class BaseMessage(BaseModel):
    """所有事件的基类"""
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    turn: int = 0
    
    @model_serializer(mode='wrap')
    def reorder_fields_serializer(self, handler) -> dict[str, Any]:
        """序列化时，将 timestamp 移动到字典的最后"""
        result = handler(self)  # 获取默认序列化结果
        
        if "timestamp" in result:
            # 弹出 timestamp 并重新插入，字典会将其排在末尾
            ts = result.pop("timestamp")
            result["timestamp"] = ts
            
        return result

class ThinkingContent(BaseMessage):
    """推理或思考内容块。

    并非每个提供商都原生暴露这种信息。当存在时，它通常
    代表模型生成的内部思考/推理轨迹（如 DeepSeek R1 的推理过程），或多轮对话继续所需的一个不透明 Token。

    Attributes:
        type (Literal["thinking"]): 内容块联合类型的鉴别符。
        thinking (str): 在可用时提供的、人类可读的内部推理和思考文本。
        thinking_signature (str | None): 特定于提供商的推理内容重用签名/标识。
        redacted (bool): 推理文本是否已被安全过滤器或特定策略脱敏/移除。
    """

    type: Literal["thinking"] = "thinking"
    thinking: str = ""
    # 例如：对于 OpenAI (o1, o3) 的响应，这可能是 reasoning 项的脱敏 ID
    thinking_signature: str | None = None
    # 当为 True 时，表示具体的思考内容已被平台方的安全过滤器脱敏/隐藏。此时不透明的
    # 加密载荷通常存储在 `thinking_signature` 中，以便能够传回 API 维持多轮上下文连续性。
    redacted: bool = False

    def pretty_line(self) -> str:
        return f"[ThinkingContent.{self.id}] | {self.thinking} " if self.thinking else ""


class TextContent(BaseMessage):
    """用户、助手和工具结果消息中使用的文本内容块。

    Attributes:
        type (Literal["text"]): 内容块联合类型的鉴别符。
        text (str): 纯文本内容实体。
        text_signature (str | None): 可选的、特定于提供商的文本签名。
            当提供商支持多轮上下文复用时，可以在后续请求中将其发回以节省 Token 成本。
    """

    type: Literal["text"] = "text"
    text: str = ""
    # 例如：对于 OpenAI 响应，这可能是消息元数据 (遗留的 id 字符串或 TextSignatureV1 JSON)
    text_signature: str | None = None

    def pretty_line(self) -> str:
        return f"[TextContent.{self.id}] | {self.text}" if self.text else ""


class ImagesContent(BaseMessage):
    """多图像内容块，支持 base64 内联数据或直接 URL 两种来源模式。

    Attributes:
        type (Literal["image"]): 内容块联合类型的鉴别符。
        source (Literal["base64", "url"]): 图像数据来源模式。
            ``"base64"`` 表示 ``data`` 字段为 base64 编码的原始图像字节；
            ``"url"`` 表示 ``data`` 字段为可直接访问的图像 URL。
        data (list[str]): base64 模式下为编码后的图像字节字符串列表；url 模式下为图像的 URL 地址列表。
        mime_type (str): 图像的 MIME 类型，如 ``"image/png"`` 或 ``"image/jpeg"``。
            url 模式下可省略（部分提供商会自动推断）。
    """

    source: Literal["base64", "url"] = "url"
    data: list[str] = Field(default_factory=list)
    # 例如："image/jpeg", "image/png"
    mime_type: str = "image/png"
    type: Literal["image"] = "image"

    def pretty_line(self) -> str:
        return f"[ImagesContent.{self.id}] | {self.data}" if self.data else ""


class VideosContent(BaseMessage):
    """视频内容块，支持 base64 内联数据或直接 URL 两种来源模式。

    Attributes:
        type (Literal["video"]): 内容块联合类型的鉴别符。
        source (Literal["base64", "url"]): 视频数据来源模式。
        data (list[str]): base64 模式下为编码后的视频字节字符串列表；url 模式下为视频 URL 列表。
        mime_type (str): 视频的 MIME 类型，如 ``"video/mp4"``。
    """

    type: Literal["video"] = "video"
    source: Literal["base64", "url"] = "url"
    data: list[str] = Field(default_factory=list)
    mime_type: str = "video/mp4"

    def pretty_line(self) -> str:
        return f"[VideosContent.{self.id}] | {self.data}" if self.data else ""


class ToolCall(BaseMessage):
    """模型助手触发的模型工具调用（函数调用）块。

    模型可以在其助手返回消息内放置一个 ``ToolCall`` 对象块，要求
    应用程序在本地执行外部工具逻辑。之后应用程序通常会执行回调，并发回
    一个匹配的 :class:`ToolResultMessage`。

    Attributes:
        type (Literal["toolCall"]): 内容块联合类型的鉴别符。
        id (str): 提供商模型生成的工具调用唯一标识符。
        name (str): 模型决定调用的目标工具函数的名称。
        arguments (dict[str, object]): 模型为工具调用生成的 JSON 格式输入参数字典。
        thought_signature (str | None): 特定于提供商的、用于重用思考上下文的可选签名。
    """

    type: Literal["toolCall"] = "toolCall"
    id: str = ""
    name: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    # 针对 Google 模型的特有字段：用于在后续复用工具调用关联思考上下文的不透明签名
    thought_signature: str | None = None

    def pretty_line(self) -> str:
        return f"[ToolCall.{self.id}] | {self.name}({self.arguments}) " if self.arguments else ""


class Cost(BaseModel):
    """标准化后的货币成本结构对象（单位通常以美元/百万Token为基础计算得出）。"""

    upstream_inference_cost: float = 0.0
    upstream_inference_prompt_cost: float = 0.0
    upstream_inference_completions_cost: float = 0.0
    # cacheWrite: float = 0.0
    # total: float = 0.0

    def pretty_line(self) -> str:
        return (f"[Cost] upstream_inference_cost={self.upstream_inference_cost} "
                f"prompt={self.upstream_inference_prompt_cost} completions={self.upstream_inference_completions_cost}")


class Usage(BaseModel):
    """标准化的 Token 使用量与对应估计成本追踪对象。"""

    completion_tokens: int = 0.0
    prompt_tokens: int = 0.0
    total_tokens: int = 0.0
    completion_tokens_details: dict[str, Any] = Field(default_factory=dict)
    prompt_tokens_details: dict[str, Any] = Field(default_factory=dict)
    cost: float = 0.0
    is_byok: bool = False
    cost_details: Cost = Field(default_factory=Cost)

    def pretty_line(self) -> str:
        return (f"[Usage] prompt={self.prompt_tokens} completion={self.completion_tokens} "
                f"total={self.total_tokens} cost=${self.cost:.6f}")


class UserMessage(BaseMessage):
    """提供给模型的，由现实人类用户或上游发出的输入消息。

    Attributes:
        role (Literal["user"]): 始终为 ``"user"``。
        content (str | list[TextContent | ImagesContent]): 消息的具体内容。可以是一个简单的普通纯文本字符串，
            也可以是包含文本和图像的结构化内容块列表（用于多模态交互）。
        timestamp (str): 消息生成的时间字符串，格式为 "%Y-%m-%d %H:%M:%S"。

    Examples:
        创建一条简易的文本消息::

            UserMessage(content="请总结这个文件。")
    """

    role: Literal["user"] = "user"
    alias: Literal["user"] = "user"
    content: str | list[TextContent | ImagesContent | VideosContent] = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def pretty_line(self) -> str:
        return f"[UserMessage.{self.id}] | {self.content}" if self.content else ""


class AssistantMessage(BaseMessage):
    """由模型生成的助手回复消息。

    这是 ``complete()`` 顶层 API 调用所返回的最终结构化消息对象，
    也是在流式处理（Streaming）模式下，在流式生成触发 ``done`` 事件时抛出的最后完整结果。

    Attributes:
        role (Literal["assistant"]): 始终为 ``"assistant"``。
        content (list[TextContent | ThinkingContent | ToolCall]): 结构化内容的有序区块列表。
            包含了模型生成的纯文本块、内部思考块以及欲调用的工具块。
        api (Api): 负责生成此网络请求所用的具体 API 分类标识（路由源）。
        provider (Provider): 实际处理请求、生成此消息的模型供应商标签。
        model (str): 提供商那侧所使用的原生底层模型标识符。
        usage (Usage): 规范化的 Token 使用情况与账单成本统计信息。
        stop_reason (StopReason): 与提供商无关的、统一标准的模型生成停止原因标识（例如 stop, length 等）。
        error_message (str | None): 可选的来自模型服务提供方 API 层的错误抛出文本。
        timestamp (str): 消息生成的时间字符串，格式为 "%Y-%m-%d %H:%M:%S"。
    """

    role: Literal["assistant"] = "assistant"
    alias: Literal["assistant"] = "assistant"
    content: list[TextContent | ThinkingContent | ToolCall] = Field(
        default_factory=list
    )
    reasoning_details: list | None = None
    api: Api = ""
    provider: Provider = ""
    model: str = ""
    usage: Usage | Any | None = None
    stop_reason: StopReason = "stop"
    error_message: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def pretty_line(self) -> str:
        if self.stop_reason == 'error':
            return f"[AssistantMessage.{self.id}] | {self.error_message}"

        lines = []
        lines.append(f"[AssistantMessage.{self.id}]")
        for block in self.content:
            lines.append(block.pretty_line())
        return " | ".join(lines)


class ToolResultMessage(BaseMessage):
    """携带来自应用端外部工具正确/错误执行结果的消息载体。

    Attributes:
        role (Literal["toolResult"]): 始终为 ``"toolResult"``。
        tool_call_id (str): 正在回复或被响应的那次具体工具调用的唯一标识。（对查 ID）
        tool_name (str): 上下文中人类所能识别的工具名称。
        content (list[TextContent | ImagesContent]): 结构化的输出执行结果反馈内容实体（文本和图片）。
        details (object | None): 额外的开发应用或服务器特定元数据（例如执行使用的时间开销等）。
        is_error (bool): 这个工具的回调执行整体是否失败或报错了。
        timestamp (str): 此回调结果装载生成的时间字符串，格式为 "%Y-%m-%d %H:%M:%S"。
    """

    role: Literal["toolResult"] = "toolResult"
    alias: Literal["toolResult"] = "toolResult"
    tool_call_id: str = ""
    tool_name: str = ""
    content: list[TextContent | ImagesContent] = Field(default_factory=list)
    # 可选的提供商特定的应用相关元数据信息（如详细的堆栈跟踪、执行耗时等）。
    details: Any = None
    is_error: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def pretty_line(self) -> str:
        lines = []
        lines.append(f"[ToolResultMessage.{self.id}] | {self.tool_name}")
        for block in self.content:
            lines.append(block.pretty_line())
        return " | ".join(lines)


Message = UserMessage | AssistantMessage | ToolResultMessage


class Tool(BaseMessage):
    """暴露给模型提供商以供模型自由调用的工具定义。

    Attributes:
        name (str): 在工具调用过程中模型可引用的函数/工具名称。
        description (str): 定义该工具功能及使用条件的人类可读文本描述（越精确越好，决定模型智商）。
        parameters (Mapping[str, object]): 描述并约束有效请求输入参数格式的 JSON Schema。
    """

    name: str
    description: str
    # 这里的 parameters 应该是合法的 JSON Schema (TSchema)
    parameters: Mapping[str, Any]
    # "parameters":
    # {
    #     "type": "object",
    #     "properties": {
    #         "departure": {
    #             "description": "出发地",
    #             "type": "string"
    #         },
    #         "destination": {
    #             "description": "目的地",
    #             "type": "string"
    #         },
    #         "date": {
    #             "description": "日期",
    #             "type": "string",
    #         }
    #     },
    #     "required": ["departure", "destination", "date"]
    # },

    def pretty_line(self) -> str:
        desc = self.description[:60] + "..." if len(self.description) > 60 else self.description
        return f"[Tool] name={self.name} description={desc!r}"


class Context(BaseMessage):
    """用于单次模型生成调用的完整会话上下文记录。

    代表了在进行提示时向提供商发起完整发送的所有相关预定义信息。

    Attributes:
        system (str | None): 位于顶层的可选系统级别指令集说明（俗称 System Prompt）。
        messages (list[Message]): 包含了用户与模型间交互历史的有顺序的对话记录列表。
        tools (list[Tool] | None): 可选的、开放给模型自主决定是否调用的可用工具外挂声明。

    Examples:
        构建一个简单的测试上下文::

            context = Context(
                system="你是一个高度精确和简洁的人工智能助手。",
                messages=[UserMessage(content="请用 Python 解释什么是生成器(generators)？")],
            )
    """

    system: str | None = None
    messages: list[Message] = Field(default_factory=list)
    tools: list[Tool] | None = None

    def pretty_line(self) -> str:
        system_preview = (self.system[:60] + "..." if self.system and len(self.system) > 60 else self.system) if self.system else None
        tool_names = [t.name for t in self.tools] if self.tools else []
        msg_types = [getattr(m, "alias", type(m).__name__) for m in self.messages]
        return (f"[Context.{self.id}] system={system_preview!r} messages={len(self.messages)} "
                f"types={msg_types[:5]} tools={tool_names}")

# Context.model_rebuild()
