"""Application configuration management

Loads settings from ~/.ado-copilot-agent/config.toml (if present) with
sensible defaults. Environment variables override config-file values.

Usage:
    from utilities.app_config import get_config
    cfg = get_config()
    print(cfg.default_model)
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import logging

_logger = logging.getLogger("ado_copilot_agent.utilities.app_config")

# Singleton cache
_config: Optional["AppConfig"] = None


@dataclass
class AppConfig:
    """Typed application configuration with defaults."""

    # LLM model used when no -m flag is passed
    default_model: str = "claude-sonnet-4.6"

    # Copilot agent execution timeout in seconds
    agent_timeout: int = 300

    # Base branch used by the develop command when no -b flag is passed
    default_base_branch: str = "qa"

    # Timeout for individual git subprocess calls in seconds
    git_timeout: int = 30

    # Azure DevOps work item state names used by each lifecycle stage
    work_item_states: dict = field(default_factory=lambda: {
        "plan": ["Active", "In Progress", "Committed"],
        "develop": ["Resolved", "In Review"],
    })

    # Ordered list of directories to search for agent .md files
    agent_search_paths: list = field(default_factory=lambda: [
        ".github/agents",
        "agents",
        "docs/agents",
        ".",
    ])


def _config_file_path() -> Path:
    return Path.home() / ".ado-copilot-agent" / "config.toml"


def _load_from_toml(path: Path) -> dict:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as e:
        _logger.warning("Could not parse config.toml (%s): %s", path, e)
        return {}


def _apply_env_overrides(cfg: AppConfig) -> None:
    """Let environment variables override config-file values."""
    if val := os.environ.get("ADO_DEFAULT_MODEL"):
        cfg.default_model = val
    if val := os.environ.get("ADO_AGENT_TIMEOUT"):
        try:
            cfg.agent_timeout = int(val)
        except ValueError:
            _logger.warning("ADO_AGENT_TIMEOUT is not an integer: %s", val)
    if val := os.environ.get("ADO_DEFAULT_BASE_BRANCH"):
        cfg.default_base_branch = val
    if val := os.environ.get("ADO_GIT_TIMEOUT"):
        try:
            cfg.git_timeout = int(val)
        except ValueError:
            _logger.warning("ADO_GIT_TIMEOUT is not an integer: %s", val)


def get_config() -> AppConfig:
    """Return the singleton AppConfig, loading it on first call."""
    global _config
    if _config is not None:
        return _config

    raw = _load_from_toml(_config_file_path())
    cfg = AppConfig(
        default_model=raw.get("default_model", AppConfig.default_model),
        agent_timeout=raw.get("agent_timeout", AppConfig.agent_timeout),
        default_base_branch=raw.get("default_base_branch", AppConfig.default_base_branch),
        git_timeout=raw.get("git_timeout", AppConfig.git_timeout),
        work_item_states=raw.get("work_item_states", AppConfig().work_item_states),
        agent_search_paths=raw.get("agent_search_paths", AppConfig().agent_search_paths),
    )
    _apply_env_overrides(cfg)
    _logger.debug(
        "AppConfig loaded: model=%s, timeout=%ds, base_branch=%s, git_timeout=%ds",
        cfg.default_model, cfg.agent_timeout, cfg.default_base_branch, cfg.git_timeout,
    )
    _config = cfg
    return _config
