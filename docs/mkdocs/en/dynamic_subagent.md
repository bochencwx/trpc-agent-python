# Dynamic Sub-Agent

Dynamic Sub-Agent lets a parent agent spawn a fresh, isolated sub-agent at run time to handle a focused task. Unlike pre-orchestrated patterns (`ChainAgent` / `ParallelAgent` / `TeamAgent`) that require all participants to be declared at construction time, the parent decides *when* and *which type* of sub-agent to spawn based on the task it sees.

## Overview

### Features

- 🚀 **Works out of the box** — `DynamicAgentTool()` requires zero configuration. The built-in `default` sub-agent (a neutral task executor) inherits all parent tools automatically.
- 📝 **Two ways to define sub-agents** — define sub-agent name, description, system prompt, and tool set via code (`SubAgentArchetype`) or Markdown files.
- 💬 **Context isolation, opt-in sharing** — sub-agents do not see the parent's conversation history by default, preventing exploratory search results and intermediate steps from polluting context. For tasks that need conversation continuity, inject parent history via `SubAgentConfig(include_parent_history=True)`.
- 🔧 **Flexible tool scope** — sub-agents can inherit all parent tools or use a specified tool set, tailoring capabilities to the task.
- ⚙️ **Unified runtime configuration** — `SubAgentConfig` controls model, max turns, and parallel tool call strategy for all sub-agents.

### When to Use vs. Other Orchestrations

| Pattern | Decision time | When to pick |
| --- | --- | --- |
| Pre-orchestrated (`ChainAgent` / `ParallelAgent` / `TeamAgent` / `GraphAgent`, etc.) | At construction | All participants and workflows are known up-front. |
| `AgentTool` | At construction | Wraps a pre-built agent as a tool; the parent invokes it by name with a fixed agent instance. |
| **Dynamic Sub-Agent** | **At run time, by the LLM** | The parent doesn't know in advance whether (or what kind of) help it needs. The LLM dynamically picks an archetype and supplies a prompt. |

## Concepts

### Archetype

A `SubAgentArchetype` is a frozen template that describes *one kind of sub-agent the parent is allowed to spawn*. It locks down the dangerous knobs (instruction, tools, model) so prompt-injected calls cannot reshape the sub-agent into something arbitrary.

```python
@dataclass(frozen=True)
class SubAgentArchetype:
    name: str                      # registry key + the value LLM passes as `subagent_type`
    description: str               # what the LLM reads to pick this archetype
    instruction: str | InstructionProvider
    tools: tuple | None = None     # None = inherit all parent tools
    model: Any = None              # None = inherit via SubAgentConfig or parent's model
```

The two text fields target different audiences:

- **`description`** — read by the **parent LLM** when selecting which archetype to spawn. Third-person, selection-focused. Recommended style: `<role summary>. Use it for <typical tasks>. Do NOT use it for <things it's bad at>. **IMPORTANT:** <hard constraints>.`
- **`instruction`** — the **sub-agent's** system prompt. Second-person, execution-focused: `You are X. Your role is ... Constraints: ...`. Supports both strings and `InstructionProvider` callables.

The framework automatically appends `(Tools: ...)` to each archetype description when rendering the `dynamic_agent` tool description. `None` renders as `(Tools: (all))`.

### Registry

`SubAgentRegistry` is the catalog the `DynamicAgentTool` reads from. It does not need to be constructed directly — `DynamicAgentTool` builds one internally at init time.

### Built-in Archetypes

Four built-in archetypes are provided:

| name | tools | typical use |
| --- | --- | --- |
| `default` | `None` (inherits all parent tools) | **Neutral task executor.** Does not impose a specific role; defers behavior to the task and tools. **The only archetype auto-registered.** |
| `general-purpose` | `None` (inherits all parent tools) | **Researcher / explorer persona**. Carries soft constraints like "NEVER create files unless absolutely necessary" — opt-in only. |
| `Explore` | `Read` / `Glob` / `Grep` / `WebFetch` | Read-only search: locate files, grep symbols, "where is X defined". |
| `Plan` | `Read` / `Glob` / `Grep` | Design implementation plans without modifying code. |

`Explore` and `Plan` share a **`_READ_ONLY_PREAMBLE`** prefix in their instruction ("CRITICAL: You are in READ-ONLY mode..."), providing defense-in-depth on top of their read-only tool sets.

Only `default` is auto-registered. `general-purpose`, `Explore`, and `Plan` must be explicitly added via the `agents` parameter.

> ⚠️ **`default` vs `general-purpose`**: both inherit parent tools (`tools=None`), but `default`'s instruction is intentionally neutral — it does not shape a specific persona. `general-purpose` is a researcher-style archetype with explicit search-first and "NEVER create files" biases. Pick `default` when you want a neutral container; pick `general-purpose` when you want the researcher persona.

## API

### `DynamicAgentTool`

The single tool the parent agent adds to enable dynamic sub-agent spawning.

```python
class DynamicAgentTool(BaseTool):
    def __init__(
        self,
        agents: list[SubAgentArchetype] | None = None,
        agent_paths: list[str | os.PathLike] | None = None,
        tool_mapping: dict[str, Any] | None = None,
        with_default: bool = True,
        agent_config: SubAgentConfig | None = None,
        skip_summarization: bool = False,
        filters_name: list[str] | None = None,
        filters: list[BaseFilter] | None = None,
    ) -> None: ...
```

| parameter | meaning |
| --- | --- |
| `agents` | Additional archetypes to register. |
| `agent_paths` | One or more directories of `*.md` files to load archetypes from disk. |
| `tool_mapping` | Custom tool name → tool class mapping for resolving tool names in MD frontmatter. Merged with the built-in whitelist; custom entries take precedence. |
| `with_default` | Whether to register the built-in `default` archetype as fallback. Default `True`. Set to `False` to fully control the archetype catalog via `agents=`. |
| `agent_config` | `SubAgentConfig` applied to every spawned sub-agent. Only non-`None` fields are forwarded to the `LlmAgent` constructor. |
| `skip_summarization` | When `True`, the parent agent's LLM loop exits immediately after the sub-agent returns, saving a summarization turn. |

The tool the LLM sees:

```
dynamic_agent — Launch a new sub-agent to handle complex, multi-step tasks.

Available subagent types:
- default: <description> (Tools: (all))
- Explore: <description> (Tools: Read, Glob, Grep, WebFetch)

Parameters:
  subagent_type: enum["default", "Explore", ...]
  prompt: str           # full task prompt for the sub-agent
  description: str      # short label (3-7 words) of what this sub-agent will do
```

> Only `prompt` varies at call time. Instruction, tool set, and model are fixed by the archetype — the LLM cannot override them.

### `SubAgentConfig`

Provides unified construction-time defaults for every spawned sub-agent. `None` means "inherit from the parent agent".

```python
@dataclass(frozen=True)
class SubAgentConfig:
    model: LLMModel | None = None
    """Model for the sub-agent. None inherits the parent's model."""

    generate_content_config: GenerateContentConfig | None = None
    """Generation config (temperature, top_p, etc.). None inherits from parent."""

    parallel_tool_calls: bool | None = None
    """Whether the sub-agent may issue parallel tool calls. None inherits from parent."""

    include_parent_history: bool = False
    """Whether to inject parent conversation history into the sub-agent's session."""

    max_parent_history_turns: int | None = None
    """Max parent turns to inject. None = unlimited. Only used when include_parent_history=True."""

    max_turns: int | None = None
    """Max LLM calls the sub-agent may make. None = unlimited."""
```

> `include_parent_history` and `max_turns` are consumed by `run_subagent` directly and are not forwarded to the `LlmAgent` constructor.

### `process_request` Behavior

`DynamicAgentTool.process_request()` injects context-appropriate instructions into the LLM request based on `agent_config.include_parent_history`:

- `include_parent_history=True`: tells the LLM "the sub-agent can see the current conversation's history".
- `include_parent_history=False` (default): tells the LLM "the sub-agent has no memory of this conversation — put everything it needs in `prompt`".

## Usage

### Minimal (zero config)

```python
from trpc_agent_sdk.agents import LlmAgent
from trpc_agent_sdk.agents.dynamic import DynamicAgentTool
from trpc_agent_sdk.runners import Runner

orchestrator = LlmAgent(
    name="main",
    model=opus_model,
    instruction="You may spawn sub-agents via dynamic_agent when a task benefits from focused context.",
    tools=[DynamicAgentTool()],
)

runner = Runner(app_name="demo", agent=orchestrator, session_service=...)
async for event in runner.run_async(user_id=..., session_id=..., new_message=...):
    ...
```

The parent immediately has `default`, which inherits all parent tools. To opt in to the `general-purpose` researcher persona, pass `agents=[GENERAL_PURPOSE_AGENT]` explicitly.

### Configuring sub-agents via SubAgentConfig

```python
from trpc_agent_sdk.agents.dynamic import DynamicAgentTool, SubAgentConfig

tools=[DynamicAgentTool(
    agent_config=SubAgentConfig(
        model=haiku_model,
        parallel_tool_calls=True,
    ),
)]
```

### Adding a custom archetype (code-defined)

```python
from trpc_agent_sdk.agents.dynamic import DynamicAgentTool, SubAgentArchetype
from trpc_agent_sdk.tools import ReadTool, GrepTool, GlobTool

security_auditor = SubAgentArchetype(
    name="security-auditor",
    description=(
        "Use this agent for security code audit and vulnerability analysis. "
        "It checks for OWASP Top 10 risks, hardcoded secrets, and unsafe API "
        "usage. Do NOT use it for general code review or style checks. "
        "**IMPORTANT:** This agent is read-only — it does not modify files."
    ),
    instruction="You are a security auditor...",
    tools=(ReadTool, GrepTool, GlobTool),
)

orchestrator = LlmAgent(
    tools=[DynamicAgentTool(agents=[security_auditor])],
    ...
)
```

### Loading archetypes from Markdown files

Place `.md` files in a directory (e.g., `.trpc_agents/`) with YAML frontmatter declaring name, description, and optional tools:

```markdown
---
name: security-auditor
description: Use for security code audit.
tools:
  - Read
  - Glob
  - Grep
---

You are a security auditor...
```

```python
tools=[DynamicAgentTool(agent_paths=[".trpc_agents/"])]
```

The `tools` field references built-in tool names. Custom tool names can be resolved via `tool_mapping`:

```python
tools=[DynamicAgentTool(
    agent_paths=[".trpc_agents/"],
    tool_mapping={"MyTool": MyCustomTool},
)]
```

### Parallel spawn

The parent agent emits multiple `dynamic_agent` tool calls in a single turn:

```
dynamic_agent(subagent_type="Explore", prompt="Find all auth handlers")
dynamic_agent(subagent_type="Explore", prompt="Find all session handlers")
```

The framework dispatches them in parallel through the existing parallel-tool-call path.

### Limiting sub-agent turns

```python
tools=[DynamicAgentTool(
    agent_config=SubAgentConfig(max_turns=3),
)]
```

When the limit is reached, the result ends with "[sub-agent stopped: max turns reached]".

### Injecting parent conversation history

```python
tools=[DynamicAgentTool(
    agent_config=SubAgentConfig(include_parent_history=True, max_parent_history_turns=3),
)]
```

The sub-agent can see the parent's last 3 turns of conversation history.

## Tool Inheritance

### `tools=None` inherits parent tools

When an archetype's `tools` is `None` (e.g., the built-in `default` and `general-purpose`), the sub-agent inherits all parent tools:

- `BaseTool` instances are shared directly (stateless).
- `BaseToolSet` instances (e.g., MCPToolset) are wrapped in `_BorrowedToolSet` so the sub-runner's `close()` cannot tear down the parent's connections.
- `DynamicAgentTool` is always stripped from the sub-agent's tool surface, preventing recursive spawning.

### `tools` specifies an independent tool set

When an archetype explicitly specifies `tools=(ReadTool, GlobTool, ...)`, the sub-agent uses only those tools and does not inherit from the parent. This is how read-only archetypes like `Explore` / `Plan` work.

## Behavior Guarantees

| Aspect | Behavior |
| --- | --- |
| **Override at call time** | Locked. Only `prompt` may be supplied; instruction / tools / model are fixed by the archetype. |
| **Batch API** | None. Parallelism is achieved via parallel tool calls. |
| **Streaming** | Hidden. The parent only observes `function_call(dynamic_agent, ...)` and `function_response(...)`; sub-agent partial events are not forwarded. |
| **Nesting** | 1-level hard cap. `DynamicAgentTool` is always stripped from the sub-agent's tool set. |
| **Session isolation** | The sub-agent runs against a fresh ephemeral session. Parent history is not shared by default — enable via `include_parent_history=True`. |
| **Memory isolation** | Memory service is not shared. Long-term memory is not visible to sub-agents. |
| **Cancellation** | The sub-agent's cancel token cascades from the parent's. Cancelling the parent run cancels in-flight sub-agents. |
| **Telemetry** | Each spawn opens a `subagent.<archetype.name>` span, attributed with `parent_invocation_id` and `subagent_type`. |
| **Result shape** | The sub-agent's final assistant text is returned as the tool result string. |

