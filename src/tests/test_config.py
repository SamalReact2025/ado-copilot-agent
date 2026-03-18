"""Tests for utilities/config.py"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch


class TestLoadEnvFromHome:
    def test_creates_config_dir_if_missing(self, tmp_path, monkeypatch):
        config_dir = tmp_path / ".ado-copilot-agent"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        from utilities.config import load_env_from_home
        returned_dir, _ = load_env_from_home()
        assert config_dir.exists()

    def test_project_env_takes_precedence(self, tmp_path, monkeypatch):
        """Values in project-level .env should override home .env values."""
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        home_env = home_dir / ".ado-copilot-agent" / ".env"
        home_env.parent.mkdir(parents=True)
        home_env.write_text("MY_TEST_VAR=from_home\n")

        project_env = project_dir / ".env"
        project_env.write_text("MY_TEST_VAR=from_project\n")

        monkeypatch.setattr(Path, "home", lambda: home_dir)
        monkeypatch.chdir(project_dir)
        monkeypatch.delenv("MY_TEST_VAR", raising=False)

        from utilities import config as cfg_module
        cfg_module.load_env_from_home()
        assert os.environ.get("MY_TEST_VAR") == "from_project"


class TestGetEnvVariable:
    def test_returns_existing_env_value(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MY_EXISTING_VAR", "hello")
        # Point env path somewhere that doesn't exist so dotenv_values returns {}
        with patch("utilities.config.get_env_path", return_value=tmp_path / "nofile.env"):
            from utilities.config import get_env_variable
            val = get_env_variable("MY_EXISTING_VAR", password=False)
        assert val == "hello"
