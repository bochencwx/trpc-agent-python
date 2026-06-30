# 动态子 Agent 工具使用示例

本示例演示如何通过 `DynamicAgentTool` 让编排 Agent 动态生成子 Agent 来完成复杂任务，支持零配置、代码定义、Markdown 文件定义三种接入方式。

## 关键特性

- **自主决策委托**：编排 Agent 携带基础工具（Read/Glob/Grep）处理简单任务，同时挂载 `DynamicAgentTool()` 用于复杂多步骤工作。模型自行判断是直接处理请求还是委托给子 Agent
- **严格隔离**：每个子 Agent 运行在全新的独立上下文中（不含父会话历史、记忆、回调），仅将最终答案作为工具结果返回给编排 Agent
- **一级嵌套上限**：子 Agent 无法再次生成子 Agent，防止无限递归
- **三种接入方式**：零配置默认模式、代码定义 Archetype、Markdown 文件定义 Archetype

## Agent 层级结构说明

```text
orchestrator (LlmAgent) — 编排 Agent
├── tools: ReadTool, GlobTool, GrepTool
├── tools: DynamicAgentTool
│   ├── default（内置，默认注册；中性任务执行者，继承父工具）
│   ├── general-purpose（内置，按需注册；研究员 / 探索者人格）
│   ├── Explore（内置，按需注册；只读搜索专家）
│   ├── Plan（内置，按需注册；只读架构师）
│   └── security-auditor（代码或 MD 自定义）
└── 共享 sample_repo/ 而非真实代码库
```

关键文件：

- [examples/dynamic_subagent/agent/agent.py](./agent/agent.py)：Agent 组装、模式分发
- [examples/dynamic_subagent/run_agent.py](./run_agent.py)：启动入口
- [examples/dynamic_subagent/.env](./.env)：模型凭据配置
- [examples/dynamic_subagent/.trpc_agents/security-auditor.md](./.trpc_agents/security-auditor.md)：MD 模式下的自定义 Archetype

## 关键代码解释

### 1) 动态子 Agent 工具挂载（`agent/agent.py`）

- **default 模式**：`DynamicAgentTool()` 零配置，仅注册中性的 `default` archetype
- **code 模式**：通过 `SubAgentArchetype` 在代码中定义 `security-auditor`，与内置的 `Explore` / `Plan` 共存（`default` 仍为兜底）
- **md 模式**：通过 `agent_paths=[".trpc_agents/"]` 从 Markdown 文件加载 Archetype，演示文件定义与内置 Archetype 的共存

### 2) 自定义 Archetype（代码定义）

```python
from trpc_agent_sdk.agents.dynamic import SubAgentArchetype
from trpc_agent_sdk.tools import ReadTool, GlobTool, GrepTool

security_auditor = SubAgentArchetype(
    name="security-auditor",
    description="Use for security code audit...",
    instruction="You are a security auditor...",
    tools=(ReadTool, GlobTool, GrepTool),
)
```

### 3) 自定义 Archetype（Markdown 文件定义）

在 `.trpc_agents/` 目录下放置 `.md` 文件，YAML 前置元数据声明名称、描述和工具列表：

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

## 环境与运行

### 环境要求

- Python 3.12

### 安装步骤

```bash
git clone https://github.com/trpc-group/trpc-agent-python.git
cd trpc-agent-python
python3 -m venv .venv
source .venv/bin/activate
pip3 install -e .
```

### 环境变量要求

在 [examples/dynamic_subagent/.env](./.env) 中配置（或通过 `export` 设置）：

- `TRPC_AGENT_API_KEY`
- `TRPC_AGENT_BASE_URL`
- `TRPC_AGENT_MODEL_NAME`

`run_agent.py` 启动时调用 `load_dotenv()`，无需手动 `export`。

### 运行命令

```bash
cd examples/dynamic_subagent

# default 模式：零配置，仅 default 内置 archetype
python run_agent.py

# code 模式：代码定义 security-auditor + 内置 Explore / Plan
python run_agent.py --mode code

# md 模式：MD 文件定义 security-auditor + 内置 Explore / Plan
python run_agent.py --mode md
```

## 运行结果（实测）

**default 模式**（`--mode default`）— 编排 Agent 拥有 Read/Glob/Grep 工具，自行决定直接处理还是委托：

1. "What does the file auth.py do?" — 简单文件读取，编排 Agent 直接处理
2. "Use a sub-agent to explore this codebase..." — 跨文件搜索，生成 `default` 子 Agent

**code 模式**（`--mode code`）— `security-auditor` 通过 `SubAgentArchetype` 代码定义，与 `Explore` / `Plan` 共存：

1. "I need a security code audit of auth.py and app.py..." — 生成 `security-auditor` 子 Agent
2. "How does authentication and user identity work in this codebase?" — 生成 `Explore` 子 Agent
3. "Design an implementation plan for regional tax rate support..." — 生成 `Plan` 子 Agent

**md 模式**（`--mode md`）— 与 code 模式相同的查询，但 `security-auditor` 从 `.trpc_agents/security-auditor.md` 加载，演示文件定义与内置 Archetype 的共存。

## 结果分析（是否符合要求）

结论：**符合本示例测试要求**。

- 三种模式均能正确注册 Archetype 并按查询路由到对应子 Agent
- 子 Agent 在隔离上下文中执行，结果正确返回给编排 Agent
- code 与 md 模式下的 security-auditor 行为一致

## 适用场景建议

- 验证动态子 Agent 的注册、路由与隔离能力：适合使用本示例
- 快速体验零配置的 `default` 子 Agent：使用 default 模式
- 测试代码定义与文件定义两种 Archetype 接入方式：使用 code / md 模式
- 需要完整的接口规范说明：参见 [`docs/mkdocs/zh/dynamic_subagent.md`](../../docs/mkdocs/zh/dynamic_subagent.md)
