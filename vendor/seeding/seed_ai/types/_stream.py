"""模型提供商适配器和应用侧代码共享的基础异步事件流（Event Stream）原语。

此模块中的核心抽象故意保持精简：

- 生产者（模型提供商）调用 ``push()`` 推入事件块、``set_result()``、``end()`` 结束流或 ``fail()`` 抛出异常；
- 消费者（应用代码）使用 ``async for`` 语法糖读取增量事件流；
- 高级调用方（如只关心最终结果的代码）在流完成时，可使用 ``await result()`` 一次性获得最终聚合好的消息对象。

这种分离干净地切分了 AI 应用中常常需要同时存在的两种消费模式：

1. 增量消费 (Incremental consumption)
   适用于命令行界面 (CLI) 对话、流式聊天 UI、进度日志输出以及工具调用过程检视。
2. 最终结果消费 (Final-result consumption)
   适用于批处理任务、自动化测试或仅需提取完整且已组装完成的助手消息数据的任务流管道。

Examples:
    以两种方式结合使用和消费模型运行流::

        event_stream = stream(model, context, options)

        # 方式一：增量式消费用于展示打字机效果
        async for event in event_stream:
            # print(event)
            pass

        # 方式二：阻塞等待获取组合完毕的完整消息体
        final_message = await event_stream.result()
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Generic, TypeVar, cast, final, overload

from ._event import AssistantMessageEvent, DoneEvent, ErrorEvent
from .message import AssistantMessage

# TEvent: 每次流式推出来的数据块（Chunk）的类型，通常是 str 或 dict (SSE解析后)
TEvent = TypeVar("TEvent")

# TResult: 最终流结束时，拼接/提取出的完整结果类型，用于存入 Context/Memory
TResult = TypeVar("TResult")


class StreamClosedError(RuntimeError):
    """用于流中断或意外终止相关问题的基本异常基类。"""


class StreamEndedWithoutResultError(StreamClosedError):
    """当流正常干净地结束，但最终没能提取或获取到有效结果对象时抛出。"""


@final
class _EndOfStream:
    """Unique sentinel used internally to stop async iteration.

    ``None`` is not used because ``None`` may be a valid event value for a
    generic stream.
    """


_EOS = _EndOfStream()
_MISSING = object()


class EventStream(AsyncIterator[TEvent], Generic[TEvent, TResult]):
    """通用的异步生产者-消费者并发流模型。

    模型厂商适配器（生产者）负责将基于底层响应的事件推送至流中，而应用层代码（消费者）
    则异步地读取它们。当提供商已知最终的结构化结果时，它
    会将该结果保存在内部的一个 Future 句柄中，以便调用者可以直接对其进行等待 (await)。

    Args:
        is_complete: 判定回调函数，当新推入的流事件表明当前应该作为流的终止事件时，应返回 ``True``。
        extract_result: 提取器回调，用于从被判定为终止事件的事件体中抽取出最终构建的结果值。

    Notes:
        底层实现利用 ``asyncio.Queue`` 作为事件投递队列，并用
        ``asyncio.Future`` 来承载最终结果。代码内部采用了一个专有的流末尾占位哨兵
        对象 (sentinel)，这使得即使在非特化泛型流中直接插入 ``None`` 值作为有效事件也不会引发意外终止。

        在迭代消费方面，该流设计为单消费者模型。如果强行用多个协程任务并发
        遍历同一个流实例，它们将会互相竞争抢同一队列里分配来的事件。
    """

    def __init__(
        self,
        is_complete: Callable[[TEvent], bool],
        extract_result: Callable[[TEvent], TResult],
    ) -> None:
        self._queue: asyncio.Queue[TEvent | _EndOfStream] = asyncio.Queue()
        self._done = False
        self._final_future: asyncio.Future[TResult] = self._create_future()

        self._is_complete = is_complete
        self._extract_result = extract_result

    def push(self, event: TEvent) -> None:
        """从生产者视角向流的内置队列中推入一个新的增量事件。

        Args:
            event: 提供商适配器生成并推送的事件实体。比如纯文本增量 (text delta)、
                内部思考内容增量 (thinking delta)、工具调用进度更新或者标识全部结束的最终完成事件。

        Notes:
            如果在入队判断时，预留的 ``is_complete`` 回调认定此 ``event`` 是终点事件，本
            方法将连带触发并解决掉维护最终结果的 Future 对象，与此同时立即向队列内部塞入
            一个专用的结束哨兵 (sentinel) 对象，让外部执行 ``async for`` 循环的消费者得以优雅安全地停止退出机制。
        """
        if self._done:
            return

        self._queue.put_nowait(event)

        if self._is_complete(event):
            self._done = True

            if not self._final_future.done():
                try:
                    final_val = self._extract_result(event)
                except Exception as exc:  # pragma: no cover - defensive guard
                    self._final_future.set_exception(exc)
                else:
                    self._final_future.set_result(final_val)

            self._queue.put_nowait(_EOS)

    @overload
    def end(self) -> None: ...

    @overload
    def end(self, result: TResult) -> None: ...

    def end(self, result: TResult | object = _MISSING) -> None:
        """人为主动地标记流已正常完成运行，并可选择在此操作中主动存入并解决最终运算结果。

        Args:
            result: 用于满足外部可能等待的 ``await result()`` 的最终完整结构化结果对象。

        Notes:
            此方法非常适用于提供商在执行正常的 ``push``（含终端事件在内）流程路径之外意外提前或延后结束的情况，
            例如：网络请求后的额外后处理(post-processing)，或主动应对服务器侧超时/业务层强行中断请求时的清场处理。

            若之前尚未保存过任何中间结果状态，且在本调用时不提供最终的有效 ``result`` 参数时直接 ``end()``，
            试图调用 :meth:`result` 方法便会直接抛出
            :class:`StreamEndedWithoutResultError` 报错，从而避免使用者一直死锁挂起等待不存在的结局。
        """
        if self._done:
            return

        self._done = True
        if not self._final_future.done():
            if result is _MISSING:
                self._final_future.set_exception(
                    StreamEndedWithoutResultError(
                        "EventStream ended without a final result. "
                        "Either push a completion event, pass result=... to "
                        "end(), or call set_result(...) before end()."
                    )
                )
            else:
                self._final_future.set_result(cast(TResult, result))

        self._queue.put_nowait(_EOS)

    def fail(self, error: Exception) -> None:
        """人为标记流执行出错或状态崩溃，并将包装好的异常向所有的结果订阅消费方抛出。

        Args:
            error: 后续通过 :meth:`result` 传播到使用者层面的原因为 Exception 异常实例。
        """
        if self._done:
            return

        self._done = True
        if not self._final_future.done():
            self._final_future.set_exception(error)

        self._queue.put_nowait(_EOS)

    async def result(self) -> TResult:
        """以异步协程的方式，阻塞并挂起等待此流结束时才能输出的核心结构化最终结果返回。

        Returns:
            TResult: 由流实例化时的提取器 ``extract_result`` 从末尾事件计算中推导得出，或者
                被代码由外部提前调用 ``end`` 所强行覆盖设定的返回值。

        Raises:
            StreamEndedWithoutResultError: 当流看起来已完整干净地停止运行但内部并没有获取/推导存储过任何最终确认的结果时抛出。
            Exception: 当有人经由 ``fail()`` 主动抛递错误报告时将连带重新向上层触发该错误。
        """
        return await self._final_future

    def set_result(self, result: TResult) -> None:
        """主动存储并解决最终验证结果，而不主动中断增量事件流。

        Args:
            result: 从 :meth:`result` 预备要返回给外部的最终完整结构化状态对象。
        """
        if not self._final_future.done():
            self._final_future.set_result(result)

    def __aiter__(self) -> EventStream[TEvent, TResult]:
        """Return this object as its own async iterator."""
        return self

    async def __anext__(self) -> TEvent:
        """Return the next event from the queue.

        Raises:
            StopAsyncIteration: When the stream reaches its sentinel value.
        """
        item = await self._queue.get()
        if item is _EOS:
            raise StopAsyncIteration
        return cast(TEvent, item)

    @staticmethod
    def _create_future() -> asyncio.Future[TResult]:
        """Create a future bound to the active or current event loop.

        Providers may construct streams slightly before a loop is running. In
        that case we fall back to the current loop object so the future is still
        created safely.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        return loop.create_future()


class AssistantMessageEventStream(EventStream[AssistantMessageEvent, AssistantMessage]):
    """特化定制以适用于专门生成并下发全量对话消息体（助手消息）流式更新的包装用流管理器子类。

    此类设计中将类型标注为 ``done`` 成功事件与 ``error`` 出错事件均直接视作足以中断流的终端信号点。
    对于 ``done`` 事件发生时，它会乖巧地负责返回附带于包裹当中的已生成最终完整版的助手消息实体；
    而对于由远程引发的 ``error`` 异常时会向外反馈周围上下文预期的报错负荷体(Payload)。
    """

    def __init__(self) -> None:
        def _is_complete(event: AssistantMessageEvent) -> bool:
            return isinstance(event, (DoneEvent, ErrorEvent))
            # return event.type in {"done", "error"}

        def _extract_result(event: AssistantMessageEvent) -> AssistantMessage:
            if isinstance(event, DoneEvent):
                return cast(DoneEvent, event).message
            return cast(ErrorEvent, event).message

        super().__init__(
            _is_complete,
            _extract_result,
        )
