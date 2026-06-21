
from __future__ import annotations

from .types._stream import AssistantMessageEventStream
from .types._provider import Api
from .types.model import Model
from .types.options import StreamOptions, ModelOptions
from .types.message import AssistantMessage, Context
from .types._container import ApiContainer
from ._api_containers.openrouter_completions import stream_openrouter_completions
from ._api_containers.uniaix_completions import stream_uniaix_completions


ApiContainerRegistry: dict[Api, ApiContainer] = \
{
    "openrouter-completions":
        ApiContainer(
            api="openrouter-completions",
            stream=stream_openrouter_completions,
            # stream=None,
        ),
    "uniaix-completions":
        ApiContainer(
            api="uniaix-completions",
            stream=stream_uniaix_completions,
            # stream=None,
        )
}

def _resolve_api_container(api: Api) -> ApiContainer:
    
    api_container = ApiContainerRegistry.get(api)
    if api_container is None:
        raise ValueError(f"No API container registered for api: {api}")
    return api_container


def stream(
    model: Model,
    context: Context,
    stream_options: StreamOptions,
    model_options: ModelOptions | None = None,
) -> AssistantMessageEventStream:

    api_container = _resolve_api_container(model.api)
    return api_container.stream(model, context, stream_options, model_options)


async def complete(
    model: Model,
    context: Context,
    stream_options: StreamOptions,
    model_options: ModelOptions | None = None,
) -> AssistantMessage:

    event_stream = stream(model, context, stream_options, model_options)
    async for event in event_stream:
        if event.type == "error":
            message = f"""
            {"-"*20}
            Error: {event.message}
            {"-"*20}
            """
            print(message)
    return await event_stream.result()
