"""全局秘钥自动探测与读取映射分发管理模块 (Env API Keys Resolver)。

此模块存在的防御性降解降耦层级意义如下：
1) 不同阵营模型厂商各自为政，制定占据私用的全然毫无规律差异极大的环境变量秘钥存放命名规范。
2) 上层极点调度框架（诸如 Agent Runtime 或 User Code）在做泛型推理流时并无心甚至极度排斥参与到这些琐碎细节硬编码之中。
3) 因此在本处隔离设置拦截点作为集中的“提供商枚举 (Provider) -> 系统硬存变量标识 (Env Var)”硬核静态映射翻译转换处理黑盒，上游使用方只需优雅传入 provider 类型呼号即可静默完成认证组装。

自动映射查表获取示例说明：
- provider 传入 `"openai"`    -> 本地伺服层自动探寻 `OPENAI_API_KEY`
- provider 传入 `"google"`    -> 本地伺服层自动探寻 `GEMINI_API_KEY`
- provider 传入 `"anthropic"` -> 按特定优先级顺序：优先高权鉴权 `ANTHROPIC_OAUTH_TOKEN`，若缺乏回退保底 `ANTHROPIC_API_KEY`
"""

from __future__ import annotations

import os

from .._cfg import ENV_MAP


def get_env_api_key(provider: str) -> str | None:
    """读取指定大模型提供商对应在操作系统运行时环境中静默注流放置的约定密钥字符串信息。

    注意限制：
        当前实现进度暂仅涵盖和对应在此刻 Python 分支版工程里所实际接纳了开发支持的所有 provider 所关联挂钩的安全建联 keys。

    Args:
        provider: 被请求的目标大模型 API 厂牌标识（例如 `openai`, `google`）。

    Returns:
        - str: 成功自系统环境变量存储区寻找到正确名称槽位的私钥完整凭证字符串。
        - None: 未能在环境深海中打捞出有效匹配，即宣告当前所要访问的该类 provider 完全不具备认证下发条件。
    """

    env_name = ENV_MAP.get(provider)
    if env_name is None:
        return None
    return os.getenv(env_name)
