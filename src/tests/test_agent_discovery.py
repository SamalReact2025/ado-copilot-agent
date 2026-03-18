"""Tests for services/agent_discovery.py"""

import pytest
from pathlib import Path
from unittest.mock import patch
from services.agent_discovery import AgentDiscoveryService
from models import AgentConfig


@pytest.fixture()
def discovery(tmp_path):
    with patch("services.agent_discovery.get_config") as mock_cfg:
        mock_cfg.return_value.agent_search_paths = [
            ".github/agents",
            "agents",
            "docs/agents",
            ".",
        ]
        yield AgentDiscoveryService(tmp_path)


class TestDiscoverAgent:
    def test_finds_agent_in_github_agents_dir(self, tmp_path, discovery):
        agent_dir = tmp_path / ".github" / "agents"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "planner.agent.md"
        agent_file.write_text("## Instructions\nPlan the work.\n")

        agent = discovery.discover_agent("plan")
        assert agent is not None
        assert agent.name == "planner"
        assert Path(agent.path) == agent_file

    def test_falls_back_to_agents_dir(self, tmp_path, discovery):
        agent_dir = tmp_path / "agents"
        agent_dir.mkdir()
        agent_file = agent_dir / "developer.agent.md"
        agent_file.write_text("## Dev instructions\n")

        agent = discovery.discover_agent("develop")
        assert agent is not None
        assert agent.name == "developer"

    def test_returns_none_when_not_found(self, tmp_path, discovery):
        # No agent files anywhere
        agent = discovery.discover_agent("review")
        assert agent is None

    def test_unknown_agent_type_returns_none(self, tmp_path, discovery):
        agent = discovery.discover_agent("nonexistent")
        assert agent is None

    def test_discover_all_returns_dict_with_all_types(self, tmp_path, discovery):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "planner.agent.md").write_text("plan")
        (agents_dir / "developer.agent.md").write_text("dev")
        (agents_dir / "reviewer.agent.md").write_text("review")

        all_agents = discovery.discover_all()
        assert set(all_agents.keys()) == {"plan", "develop", "review"}
        assert all(v is not None for v in all_agents.values())
