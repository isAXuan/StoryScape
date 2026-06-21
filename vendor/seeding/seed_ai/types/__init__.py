"""基础抽象数据模型与类型提示定义模块。

该模块定义了框架与各模型提供商之间交互的核心数据结构，
包括消息历史记录(`message`)、流式块事件(`event`)以及配置与抽象的通用设置(`options`)。
所有的类均为跨提供商的标准化形态，由具体的适配器在发送和接收时进行双向转换。
"""

from ._container import (
    ApiStreamFunction,
    ApiContainer
)
from ._event import (
    AssistantMessageEvent,
    StartEvent,
    TextStartEvent,
    TextDeltaEvent,
    TextEndEvent,
    ThinkingStartEvent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ToolCallStartEvent,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    DoneEvent,
    ErrorEvent,
)
from ._provider import (
    Api,
    Id,
    Provider,
)
from ._stream import (
    EventStream,
    AssistantMessageEventStream,
)
from .message import (
    ThinkingContent,
    TextContent,
    ImagesContent,
    VideosContent,
    ToolCall,
    Cost,
    Usage,
    UserMessage,
    AssistantMessage,
    ToolResultMessage,
    Message,
    Tool,
    Context,
)
from .model import (
    Model,
    ModelCost,
)
from .options import (
    ModelOptions,
    StopReason,
    StreamOptions,
    ApiOptions,
    ToolChoiceMode,
)
