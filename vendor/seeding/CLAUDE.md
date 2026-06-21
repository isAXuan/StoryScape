# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PiAgentX is a Python AI agent framework with two core modules:
- **pi_ai**: LLM API abstraction layer with multi-provider support (OpenRouter, etc.)
- **pi_agent**: High-level agent orchestration with tool execution, context compression, and event hooks

## Running Tests

```bash
python quick_pi_agent.py      # pi_agent demo (tool patterns + agent integration)
python quick_pi_ai.py          # pi_ai demo (stream/complete API)
```

## Architecture

### pi_ai — LLM API Layer

- `stream.py`: Entry point exposing `stream()` and `complete()` functions that route to provider-specific containers
- `_api_containers/`: Provider adapters (OpenRouter, etc.) implementing `ApiContainer.stream()` and `ApiContainer.complete()`
- `types/`: Message types (`UserMessage`, `AssistantMessage`, `ToolResultMessage`, `Context`) and model definitions

Stream event order for UI rendering: `Start → thinking_start → thinking_delta → thinking_end → text_start → text_delta → text_end → toolcall_start → toolcall_delta → toolcall_end → done/error`

### pi_agent — Agent Orchestration

- `agent.py`: Main `Agent` class — subscribe to events, call `agent.query()` to interact
- `_engine/loop.py`: Core `run_agent_loop()` async coroutine — orchestrates streaming, tool execution, compression
- `_engine/executor.py`: Tool call execution — invokes tools and returns `ToolResultMessage` objects
- `_engine/compressor.py`: Context compression when token count exceeds `model.compress_tokens` threshold
- `_engine/llm_stream.py`: Streams LLM responses into the agent loop
- `types/state.py`: `AgentState` — global agent state snapshot with context persistence to `agent_state.json` + `context.jsonl`
- `types/hooks.py`: `AgentHooks` — before_run, before_turn, after_turn callbacks for extension
- `types/events.py`: `EventEmitter` — pub/sub event system for UI progress updates
- `types/queue.py`: `SteeringQueue` — priority queue for injecting messages into the agent loop
- `types/message.py`: `AgentContext` and `AgentMessage` types
- `types/tool.py`: `AgentTool` base class + `@tools` decorator for defining tools

### Tool Definition Patterns

Tools support 4 patterns (see `quick_pi_agent.py` for full matrix):

| Pattern | Class Protocol | @tools Decorator |
|---------|---------------|------------------|
| BaseModel params | `params["key"]` | `params.value` |
| Flat args | `a, b` kwargs | `a, b` kwargs |

### State Persistence

`AgentState` auto-saves to `work_root/` on init and update:
- `agent_state.json`: Model config, stream options, runtime flags, turn counters
- `context.jsonl`: System, tools, and message history (append-only for messages)

## Key Files

- `pi_agent/agent.py` — Main Agent entry point
- `pi_agent/_engine/loop.py` — Core agent loop
- `pi_agent/types/state.py` — AgentState with persistence
- `pi_agent/types/hooks.py` — AgentHooks extension points
- `pi_ai/stream.py` — pi_ai public API
