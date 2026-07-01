# Tencent is pleased to support the open source community by making trpc-agent-python available.
#
# Copyright (C) 2026 Tencent. All rights reserved.
#
# trpc-agent-python is licensed under the Apache License Version 2.0.
#
"""Smoke tests for the dynamic sub-agent package import surface."""

from __future__ import annotations

import sys


def test_public_imports() -> None:
    from trpc_agent_sdk.agents.dynamic import (
        SpawnSubAgentTool,
        DEFAULT_AGENT,
        EXPLORE_AGENT,
        GENERAL_PURPOSE_AGENT,
        PLAN_AGENT,
        DynamicAgentTool,
        SubAgentArchetype,
        SubAgentRegistry,
    )
    assert SpawnSubAgentTool is not None
    assert DynamicAgentTool is not None
    assert SubAgentArchetype is not None
    assert SubAgentRegistry is not None
    assert DEFAULT_AGENT.name == "default"
    assert GENERAL_PURPOSE_AGENT.name == "general-purpose"
    assert EXPLORE_AGENT.name == "Explore"
    assert PLAN_AGENT.name == "Plan"


def test_dynamic_not_loaded_when_only_agents_imported() -> None:
    """Importing trpc_agent_sdk.agents must not eagerly pull in `dynamic`.

    The dynamic subsystem brings in file_tools / web tools — keep those off
    the default agents import path.
    """
    # Drop any cached entries for a clean check; sub-modules already loaded
    # by other tests in this run would otherwise pollute the result.
    for mod in list(sys.modules):
        if mod.startswith("trpc_agent_sdk.agents.dynamic"):
            del sys.modules[mod]

    import trpc_agent_sdk.agents  # noqa: F401

    assert "trpc_agent_sdk.agents.dynamic" not in sys.modules
