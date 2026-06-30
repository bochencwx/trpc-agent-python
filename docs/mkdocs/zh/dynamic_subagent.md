# Dynamic Sub-Agent（动态子 Agent）

Dynamic Sub-Agent 让父 agent 在运行时按需创建一个全新且隔离的子 agent，用于处理一个聚焦的子任务。与预编排模式（`ChainAgent` / `ParallelAgent` / `TeamAgent`，要求所有参与者在构造期就声明完毕）不同，Dynamic Sub-Agent 由父 agent 在执行过程中根据所见任务自行决定**何时**以及**用哪种类型**的子 agent。

## 概述

### 功能特性

- 🚀 **开箱即用** —— `DynamicAgentTool()` 无需任何配置即可使用，内置 `default` 子 agent（中性任务执行者），自动继承父 agent 的所有工具。
- 📝 **两种方式自定义子 agent** —— 可以通过代码（`SubAgentArchetype`）或 Markdown 文件定义子 agent 的名称、描述、系统提示和工具集。
- 💬 **上下文隔离，按需共享** —— 子 agent 默认看不到父 agent 的会话历史，避免探索性搜索等中间结果污染上下文。对于需要延续对话状态的任务，可通过 `SubAgentConfig(include_parent_history=True)` 将父会话历史注入子 agent。
- 🔧 **灵活控制工具范围** —— 子 agent 可以继承父 agent 的全部工具，也可以只使用指定的工具集，按场景裁剪能力。
- ⚙️ **统一配置运行时参数** —— 通过 `SubAgentConfig` 统一设置子 agent 的模型、最大调用轮数和并行工具调用策略。

### 与其他编排方式的取舍

| 模式 | 决策时机 | 适用场景 |
| --- | --- | --- |
| 预编排（`ChainAgent` / `ParallelAgent` / `TeamAgent` / `GraphAgent` 等） | 构造期 | 参与者和协作流程在事先已知。 |
| `AgentTool` | 构造期 | 将预先构建的子 agent 包装为工具，父 agent 按名调用，子 agent 实例固定。 |
| **Dynamic Sub-Agent** | **运行时，由 LLM 决策** | 父 agent 事先不知道是否需要帮助、需要哪一种帮助，由 LLM 根据任务动态选择 archetype 并传入 prompt。 |

## 概念

### Archetype（子 agent 原型）

`SubAgentArchetype` 是一个不可变模板，描述**父 agent 被允许创建的某一种子 agent**。它把容易被滥用的可调项（instruction / tools / model）锁死，使被 prompt 注入的调用无法把子 agent 重塑为任意形态。

```python
@dataclass(frozen=True)
class SubAgentArchetype:
    name: str                      # registry key，也是 LLM 传入的 `subagent_type` 值
    description: str               # 给父 LLM 看的"何时使用此 archetype"判断标准
    instruction: str | InstructionProvider  # 子 agent 自身的 system prompt
    tools: tuple | None = None     # None 表示继承父 agent 的全部工具
    model: Any = None              # None 表示通过 SubAgentConfig 或继承父 agent 的模型
```

两个文本字段面向不同的受众，写法明显不同：

- **`description`**：父 LLM 在 `dynamic_agent` 工具描述里读到，第三人称、面向选择决策。建议写法：`<角色概要>。Use it for <典型任务>。Do NOT use it for <不擅长的事>。**IMPORTANT:** <硬约束>。`
- **`instruction`**：子 agent 自己的 system prompt，第二人称、面向工作执行：`You are X. Your role is ... Constraints: ...`。支持字符串或 `InstructionProvider` 可调用对象。

框架在渲染 `dynamic_agent` 工具描述时，会自动在每个 archetype `description` 末尾追加 `(Tools: ...)`，其中 `None` 渲染为 `(Tools: (all))`，让 LLM 能够推理出能力边界。

### Registry（注册表）

`SubAgentRegistry` 是 `DynamicAgentTool` 读取 archetype 的目录。在 v1 中无需手动构造 —— `DynamicAgentTool` 会在初始化时自动构建注册表。

### 内置 Archetype

框架提供四种内置 archetype：

| name | tools | 典型用途 |
| --- | --- | --- |
| `default` | `None`（继承父 agent 全部工具） | **中性任务执行者**：不塑造特定人格，按 prompt 和工具完成任务。这是**唯一默认注册**的 archetype。 |
| `general-purpose` | `None`（继承父 agent 全部工具） | **多步研究员人格**：搜索代码、分析文件、多步调研。instruction 中带"NEVER create files unless absolutely necessary"等软约束。 |
| `Explore` | `Read` / `Glob` / `Grep` / `WebFetch` | 只读搜索：定位文件、grep 符号、回答 "X 在哪定义"。 |
| `Plan` | `Read` / `Glob` / `Grep` | 设计实现方案，不修改代码。 |

`Explore` 与 `Plan` 在 `instruction` 中携带统一的 **`_READ_ONLY_PREAMBLE`** 前缀（"CRITICAL: You are in READ-ONLY mode..."），在 prompt 层面对子 agent 做防御性约束（叠加在工具集已经只读的基础上）。

仅 `default` 默认注册。`general-purpose` / `Explore` / `Plan` 都需要手动通过 `agents` 参数注册。

> ⚠️ **`default` vs `general-purpose` 的区别**：两者都 `tools=None` 继承父工具，但 `default` 的 instruction **不塑造特定人格**——它把行为完全交给任务和工具决定。`general-purpose` 是"研究员"型档案，instruction 有明确的 search-first / "NEVER create files" 偏置。需要中性容器选 `default`，需要研究员行为选 `general-purpose`。

## API

### `DynamicAgentTool`

`DynamicAgentTool` 是父 agent 启用动态子 agent 能力时唯一需要添加的工具。

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

| 参数 | 含义 |
| --- | --- |
| `agents` | 额外注册的 archetype 列表。 |
| `agent_paths` | 包含 `*.md` 文件的一个或多个目录，从磁盘加载 archetype。 |
| `tool_mapping` | 自定义工具名到工具类的映射，用于解析 MD 文件中引用的工具名。与内置白名单合并，自定义条目优先。 |
| `with_default` | 是否注册内置 `default` archetype 作为通用回退。默认 `True`。设为 `False` 时完全由用户通过 `agents=` 控制档案库。 |
| `agent_config` | 应用于每个子 agent 的 `SubAgentConfig`，仅非 `None` 字段会转发到 `LlmAgent` 构造函数。 |
| `skip_summarization` | 为 `True` 时，父 agent 的 LLM 循环在子 agent 返回后立即退出，省去一轮总结 token 开销。 |

LLM 看到的工具描述（自动渲染）：

```
dynamic_agent —— 创建一个全新且隔离的子 agent 处理一个聚焦的子任务。

可用的 subagent 类型：
- default: <description> (Tools: (all))
- Explore: <description> (Tools: Read, Glob, Grep, WebFetch)

参数：
  subagent_type: enum["default", "Explore", ...]
  prompt: str           # 给子 agent 的完整任务描述
  description: str      # 短标签（3-7 个词），描述子 agent 将做什么
```

> 调用时仅 `prompt` 可变。instruction、工具集、模型均由 archetype 锁定，LLM 无法 override。

### `SubAgentConfig`

`SubAgentConfig` 为每个子 agent 提供统一的构造期默认值。`None` 表示继承父 agent 的对应配置。

```python
@dataclass(frozen=True)
class SubAgentConfig:
    model: LLMModel | None = None
    """子 agent 使用的模型。None 继承父 agent 的模型。"""

    generate_content_config: GenerateContentConfig | None = None
    """生成配置（temperature、top_p 等）。None 继承父 agent 配置。"""

    parallel_tool_calls: bool | None = None
    """子 agent 是否可并行调用工具。None 继承父 agent 配置。"""

    include_parent_history: bool = False
    """是否将父 agent 的会话历史注入子 agent 的 session。"""

    max_parent_history_turns: int | None = None
    """注入的最大父会话轮数。None = 不限制。仅在 include_parent_history=True 时生效。"""

    max_turns: int | None = None
    """子 agent 最多可发起的 LLM 调用次数。None = 不限制。"""
```

> include_parent_history 与 max_turns 是 SubAgentConfig 字段，不会被转发到 LlmAgent 构造函数，而是由 run_subagent 直接消费。

### `process_request` 行为

`DynamicAgentTool.process_request()` 会根据 `agent_config.include_parent_history` 自动注入不同的 `llm_request` 指令：

- `include_parent_history=True`：提示 LLM "子 agent 可以看到当前会话的历史记录"。
- `include_parent_history=False`（默认）：提示 LLM "子 agent 没有此会话的记忆，需将全部上下文放入 prompt"。

## 使用方式

### 最简（零配置）

```python
from trpc_agent_sdk.agents import LlmAgent
from trpc_agent_sdk.agents.dynamic import DynamicAgentTool
from trpc_agent_sdk.runners import Runner

orchestrator = LlmAgent(
    name="main",
    model=opus_model,
    instruction="当某个任务适合在隔离上下文中处理时，可通过 dynamic_agent 创建子 agent。",
    tools=[DynamicAgentTool()],
)

runner = Runner(app_name="demo", agent=orchestrator, session_service=...)
async for event in runner.run_async(user_id=..., session_id=..., new_message=...):
    ...
```

父 agent 自动获得 `default` 子 agent，继承父 agent 的全部工具。如需 `general-purpose` 研究员档案，通过 `agents=[GENERAL_PURPOSE_AGENT]` 显式添加。

### 通过 SubAgentConfig 配置子 agent

```python
from trpc_agent_sdk.agents.dynamic import DynamicAgentTool, SubAgentConfig

tools=[DynamicAgentTool(
    agent_config=SubAgentConfig(
        model=haiku_model,
        parallel_tool_calls=True,
    ),
)]
```

### 追加自定义 Archetype（代码定义）

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

### 从 Markdown 文件加载 Archetype

在目录（如 `.trpc_agents/`）下放置 `.md` 文件，YAML 前置元数据声明 name / description 和可选的 tools 列表：

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

`tools` 字段引用内置工具名。若需要自定义工具名，可通过 `tool_mapping` 参数映射：

```python
tools=[DynamicAgentTool(
    agent_paths=[".trpc_agents/"],
    tool_mapping={"MyTool": MyCustomTool},
)]
```

### 并发 spawn

父 agent 在同一个 turn 中发出多个 `dynamic_agent` 工具调用，无需额外 API：

```
dynamic_agent(subagent_type="Explore", prompt="找出所有 auth handler")
dynamic_agent(subagent_type="Explore", prompt="找出所有 session handler")
```

框架通过现有的 parallel tool call 路径并发派发；每个子 agent 在各自隔离的 `InvocationContext` 中运行。

### 控制子 agent 调用轮数

```python
tools=[DynamicAgentTool(
    agent_config=SubAgentConfig(max_turns=3),
)]
```

子 agent 达到 max_turns 限制后返回 "[sub-agent stopped: max turns reached]" 标记。

### 注入父会话历史

```python
tools=[DynamicAgentTool(
    agent_config=SubAgentConfig(include_parent_history=True, max_parent_history_turns=3),
)]
```

子 agent 能看到父 agent 最近的 3 轮对话历史，适合需要上下文的委托任务。

## 工具继承

### `tools=None` 继承父工具

当 archetype 的 `tools` 为 `None`（如内置的 `default` 和 `general-purpose`），子 agent 继承父 agent 的全部工具：

- `BaseTool` 实例直接共享（无状态）。
- `BaseToolSet` 实例（如 MCPToolset）通过 `_BorrowedToolSet` 包装，确保子 runner 关闭时不会误关父 agent 的连接。
- `DynamicAgentTool` 始终从子 agent 的工具集中移除，防止递归 spawn。

### `tools` 指定独立工具集

当 archetype 显式指定 `tools=(ReadTool, GlobTool, ...)`，子 agent 只使用这些工具，不继承父 agent 的工具。这是 `Explore` / `Plan` 等只读 archetype 的实现方式。

## 行为约定

| 维度 | 行为 |
| --- | --- |
| **调用时 override** | 锁定。仅可传 `prompt`；instruction / tools / model 由 archetype 固定。 |
| **批量 API** | 不提供。并行性通过 parallel tool call 实现。 |
| **流式输出** | 隐藏。父 agent 仅观察到 `function_call(dynamic_agent, ...)` 与 `function_response(...)`；子 agent 的 partial event 不会被透传。 |
| **嵌套** | 1 层硬限。子 agent 的工具集中不会包含 `DynamicAgentTool`。 |
| **会话隔离** | 子 agent 在全新临时会话中运行；默认不共享父 agent 的消息历史。可通过 `include_parent_history=True` 注入。 |
| **Memory 隔离** | 不共享 memory service；子 agent 看不到长期记忆。 |
| **取消** | 子 agent 的 cancel token 由父级级联派生。父 run 取消时，进行中的子 agent 同步取消；tool result 反映取消状态。 |
| **遥测** | 每次 spawn 开启一个 `subagent.<archetype.name>` span，attribute 包含 `parent_invocation_id` 与 `subagent_type`。 |
| **结果形态** | 子 agent 的最终 assistant 文本作为 tool result 字符串返回。不做结构化事件回放。 |

