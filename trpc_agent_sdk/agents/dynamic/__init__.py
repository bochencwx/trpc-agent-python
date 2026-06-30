# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#
"""Dynamic sub-agent subsystem.

Public API:
    - ``DynamicAgentTool`` — drop into ``LlmAgent.tools`` to enable dynamic spawning.
    - ``SubAgentArchetype`` / ``SubAgentRegistry`` — register custom archetypes.
    - ``DEFAULT_AGENT`` — neutral built-in archetype, auto-registered.
    - ``GENERAL_PURPOSE_AGENT`` / ``EXPLORE_AGENT`` / ``PLAN_AGENT`` —
      opt-in built-in archetypes (research / read-only search / read-only
      planning). Pass them via ``agents=[...]`` to register.
    - ``load_archetypes_from_dir`` / ``load_archetype_from_file`` — load archetypes
      from ``.md`` files on disk (pass ``agent_paths`` to ``DynamicAgentTool``
      instead of calling these directly).

This package is **not** re-exported from ``trpc_agent_sdk.agents`` to keep the
default agents import path free of file_tools / web tools dependencies.
"""

from ._archetype import SubAgentArchetype
from ._defaults import DEFAULT_AGENT
from ._defaults import EXPLORE_AGENT
from ._defaults import GENERAL_PURPOSE_AGENT
from ._defaults import PLAN_AGENT
from ._dynamic_tool import DynamicAgentTool
from ._loader import load_archetype_from_file
from ._loader import load_archetypes_from_dir
from ._registry import SubAgentRegistry
from ._sub_agent_config import SubAgentConfig

__all__ = [
    "DynamicAgentTool",
    "SubAgentArchetype",
    "SubAgentRegistry",
    "DEFAULT_AGENT",
    "GENERAL_PURPOSE_AGENT",
    "EXPLORE_AGENT",
    "PLAN_AGENT",
    "SubAgentConfig",
    "load_archetype_from_file",
    "load_archetypes_from_dir",
]
