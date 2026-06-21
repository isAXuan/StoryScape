"""核心智能体全局状态快照，大坝式的架构字典防腐隔离层。"""

from __future__ import annotations

import json
import uuid
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from pathlib import Path
from typing import Any

from seed_ai import Model, StreamOptions, ModelOptions

from .message import AgentContext, AgentMessage, agent_message_adapter
from .tool import AgentTool


class AgentState(BaseModel):
    """【全局主板】：智能体的运行全貌主控板 (全程生命周期管理与快照归档使用)"""

    # === 1. 认知与外设驱动配置 (Capabilities) ===
    work_root: str
    model: Model | None = None
    context: AgentContext | None = None
    stream_options: StreamOptions | None = None
    model_options: ModelOptions | None = None

    # === 2. 节拍与挂起状态池 (Runtime & Pending) ===
    is_running: bool = False
    # is_paused 人工干预悬挂态：表明模型撞击了需要 Human-in-the-loop 的敏感节点被强制挂机冻结。
    is_paused: bool = False
    is_aborted: bool = False  # 外部强杀标志位
    pending_tool_calls: set[str] = Field(default_factory=set)
    stream_message: AgentMessage | None = None

    # === 3. 安全防护与容回灾保留 (Safety) ===
    error: str | None = None
    max_auto_turn: int = 1500
    cur_turn: int = 0

    # === 4. 元数据 (Metadata) ===
    metadata: dict[str, Any] = Field(default_factory=dict)


    @model_validator(mode='after')
    def __post_init__(self):
        # 这里面的函数会在实例创建后自动运行
        self._loads()
        if not self.model or not self.stream_options:
            raise ValueError("AgentState: model and stream_options are required.")
        self._init_saves()
        return self

    def _load_context(self) -> bool:
        """从 JSONL 加载 context (system, tools, messages)。"""

        jsonl_path = Path(self.work_root) / "context.jsonl"
        if not jsonl_path.exists():
            return False

        all_messages = []
        system = None
        tools = []
        try:
            content = jsonl_path.read_text("utf-8")
            for line in content.strip().split("\n"):
                if not line.strip():
                    continue
                entry = json.loads(line)
                # 加载 system
                if "system" in entry:
                    system = entry["system"]
                    continue
                # 加载 tools（存储为 Python list 的字符串表示）
                if "tool" in entry:
                    try:
                        tools.append(AgentTool(**entry["tool"]))
                    except Exception as e:
                        print(e)
                    continue
                # 加载 messages
                all_messages.append(agent_message_adapter.validate_python(entry.get("message", [])))
        except Exception as e:
            print(e)
            pass

        # 赋值 self.context
        if not self.context:
            self.context = AgentContext(
                system=system,
                tools=tools,
                messages=all_messages,
            )
        else:
            if not self.context.system:
                self.context.system = system
            if not self.context.tools:
                self.context.tools = tools
            if not self.context.messages:
                self.context.messages = all_messages
        return True

    def _model_to_dict(self, obj: Any) -> dict | None:
        """将 model / stream_options / model_options 序列化为 dict。"""
        if obj is None:
            return None
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        return {"_raw": str(obj)}

    def _loads(self) -> bool:
        """从 work_root, agent_state.json + context.jsonl 文件加载完整状态（全量读取）。
        """
        if not self._load_context():
            return False
        
        json_path = Path(self.work_root) / "agent_state.json"
        if not json_path.exists():
            return False
        
        state = json.loads(json_path.read_text("utf-8"))
        if self.model:
            state["model"].update(self._model_to_dict(self.model))
        self.model = Model(**state["model"])   
        if self.stream_options:
            state["stream_options"].update(self._model_to_dict(self.stream_options))
        self.stream_options = StreamOptions(**state["stream_options"])
        if self.model_options:
            state["model_options"].update(self._model_to_dict(self.model_options))
        self.model_options = ModelOptions(**state["model_options"])
        return True

    def _init_saves(self) -> None:
        """将完整状态序列化为 JSON 文件（全量保存）。

        Args:
            path: 保存路径
        """
        dir_path = Path(self.work_root)
        dir_path.mkdir(parents=True, exist_ok=True)

        json_path = dir_path / "agent_state.json"
        json_path.write_text(self.model_dump_json(indent=2), "utf-8")

        jsonl_path = dir_path / "context.jsonl"
        lines = [
            json.dumps({"system": str(self.context.system)}, ensure_ascii=False),
            *[json.dumps({"tool": tool.model_dump()}, ensure_ascii=False) for tool in self.context.tools]
        ]
        for message in self.context.messages:
            lines.append(json.dumps({"message": message.model_dump()}, ensure_ascii=False))

        jsonl_path.write_text("\n".join(lines) + "\n", "utf-8")

        f=1

    # ── context 持久化（ update_context: 增量 JSONL ）──────────────────────────────────
    def update_context(self, messages: AgentMessage | list[AgentMessage], compress_range: tuple[int, int] | None = None) -> None:
        """
        compress_range: 压缩范围，(start, end)。
        如果为 None，则追加写入 messages , 否则重写 compress_range 范围内的 messages。
        """
        if not messages:
            return

        dir_path = Path(self.work_root)
        dir_path.mkdir(parents=True, exist_ok=True)
        jsonl_path = dir_path / "context.jsonl"

        if not isinstance(messages, list):
            messages = [messages]
        for message in messages:
            message.turn = self.cur_turn

        if not compress_range:
            self.context.messages.extend(messages)
            lines = [json.dumps({"message": message.model_dump()}, ensure_ascii=False) for message in messages]
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write('\n'.join(lines) + '\n')
            return

        existing_messages = self.context.messages[compress_range[0]:compress_range[1]]
        self.context.messages = messages

        # 对历史的 self.context.messages 重写 JSON 文件
        now_str = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8]  # 生成唯一ID
        json_path = dir_path / f"{now_str}_{unique_id}.json"
        json_path.write_text(json.dumps([em.model_dump() for em in existing_messages], ensure_ascii=False, indent=2), "utf-8")

        # 对新的 self.context.messages 重写 JSONL
        lines = [
            json.dumps({"system": str(self.context.system)}, ensure_ascii=False),
            *[json.dumps({"tool": tool.model_dump()}, ensure_ascii=False) for tool in self.context.tools]
        ]
        for message in self.context.messages:
            lines.append(json.dumps({"message": message.model_dump()}, ensure_ascii=False))
        jsonl_path.write_text("\n".join(lines) + "\n", "utf-8")


