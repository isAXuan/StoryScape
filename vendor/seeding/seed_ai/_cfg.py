"""配置模块。"""
from __future__ import annotations

# 环境变量映射：provider -> 环境变量名
ENV_MAP: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "google": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}