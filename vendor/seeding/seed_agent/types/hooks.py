"""引擎生命周期的劫持与拦截钩子池。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from seed_agent.types.state import AgentState

class AgentHooks:
    """提供给开发者重写以拦截干预 Agent Loop 流转的策略基类。
    区别于 Event 只有只读播报权限，所有 Hook 方法入参可直接对其产生合规的数据修改与阻断。
    """
    async def loop_before(self, state: 'AgentState') -> 'AgentState':
        """【循环打火】在开启大循环前第一时间执行。可用于统一初始化第三方资源。"""
        return state

    async def loop_break(self, state: 'AgentState') -> bool:
        """【循环打火】在开启大循环前第一时间执行。可用于统一初始化第三方资源。"""
        cnt = 0
        for msg in state.context.messages:
            if msg.turn == state.cur_turn:
                cnt += 1
        print("\n[loop_break]:", cnt)
        return False

    async def turn_start(self, state: 'AgentState') -> 'AgentState':
        """【回合起步】每次循环迭代起步（整合了 steer 急件之后）被触发。"""
        return state

    async def user_update_before(self, p_msg: 'AgentState') -> 'AgentState':
        """【入队前】Steering queue 中的消息在被处理之前触发。"""
        return p_msg

    async def user_update_after(self, p_msg: 'AgentState') -> 'AgentState':
        """【入队后】Steering queue 中的消息在被处理之后触发。"""
        return p_msg

    async def llm_stream_before(self, state: 'AgentState') -> 'AgentState':
        """【底层换包】llm 发包的前一秒拦截拦截站！
        RAG 检索增强插槽，拦截即发给远端的 context，修改 Prompt 或注入隐藏知识片后返回。
        """
        return state

    async def llm_stream_after(self, state: 'AgentState') -> 'AgentState':
        """【LLM 响应后】LLM 响应完成后触发。"""
        return state

    async def tool_calls_before(self, state: 'AgentState') -> 'AgentState':
        """【刀下留人】大模型要求执行工具，这在本地真正启动前被触发。
        允许过滤剔除、鉴权拦截不合规的 ToolCall。
        """
        return state

    async def tool_calls_after(self, state: 'AgentState') -> 'AgentState':
        """【工具执行后】工具执行完毕后触发。"""
        return state

    async def compress_before(self, state: 'AgentState') -> 'AgentState':
        """【压缩前】在 context 压缩之前触发。"""
        return state

    async def compress_after(self, state: 'AgentState') -> 'AgentState':
        """【压缩后】在 context 压缩之后触发。"""
        return state

    # async def turn_end_before(self, state: 'AgentState') -> 'AgentState':
    #     """【回合清算前】本轮完毕，LLM也回答了，该执行的 Tool 也执行了。
    #     返回 True 可以强行制止继续循环（哪怕是模型意图继续用工具，也能强杀）。
    #     """
    #     return state

    # async def turn_end_after(self, state: 'AgentState') -> 'AgentState':
    #     """【回合清算后】本轮循环结束之后触发。"""
    #     return state
