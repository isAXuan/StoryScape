"""负责 Agent 的打断和随从消息队列处理及消费策略缓冲网。"""

from typing import Any, Literal, cast
from ..types.message import AgentMessage

class SteeringQueue:
    def __init__(
        self,
        steering_mode: Literal["all", "one-at-a-time"] = "one-at-a-time",
        follow_up_mode: Literal["all", "one-at-a-time"] = "one-at-a-time",
    ) -> None:
        self.steering_mode = steering_mode
        self.follow_up_mode = follow_up_mode

        self._steering_queue: list[AgentMessage] = []
        self._follow_up_queue: list[AgentMessage] = []

    def set_steering_mode(self, mode: str) -> None:
        if mode not in {"one-at-a-time", "all"}:
            raise ValueError("steering mode must be 'one-at-a-time' or 'all'")
        self.steering_mode = cast(Any, mode)

    def set_follow_up_mode(self, mode: str) -> None:
        if mode not in {"one-at-a-time", "all"}:
            raise ValueError("follow-up mode must be 'one-at-a-time' or 'all'")
        self.follow_up_mode = cast(Any, mode)

    def steer(self, message: AgentMessage) -> None:
        self._steering_queue.append(message)

    def follow_up(self, message: AgentMessage) -> None:
        self._follow_up_queue.append(message)

    def clear_steering_queue(self) -> None:
        self._steering_queue = []

    def clear_follow_up_queue(self) -> None:
        self._follow_up_queue = []

    def clear_all_queues(self) -> None:
        self._steering_queue = []
        self._follow_up_queue = []

    def has_queued_messages(self) -> bool:
        return bool(self._steering_queue or self._follow_up_queue)

    def dequeue_steering_messages(self) -> list[AgentMessage]:
        if self.steering_mode == "one-at-a-time":
            if not self._steering_queue:
                return []
            return [self._steering_queue.pop(0)]
        out = [*self._steering_queue]
        self._steering_queue = []
        return out

    def dequeue_follow_up_messages(self) -> list[AgentMessage]:
        if self.follow_up_mode == "one-at-a-time":
            if not self._follow_up_queue:
                return []
            return [self._follow_up_queue.pop(0)]
        out = [*self._follow_up_queue]
        self._follow_up_queue = []
        return out
