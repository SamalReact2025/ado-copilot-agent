"""Tests for services/git_service.py"""

import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from services.git_service import GitService


@pytest.fixture()
def git(tmp_path):
    # Patch get_config so GitService can be instantiated without a real config file
    with patch("services.git_service.get_config") as mock_cfg:
        mock_cfg.return_value.git_timeout = 30
        yield GitService(tmp_path)


def _make_run_result(returncode: int, stdout: str = "", stderr: str = ""):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


class TestRunGit:
    def test_success_returns_true_and_stdout(self, git):
        with patch("subprocess.run", return_value=_make_run_result(0, stdout="main")) as mock_run:
            ok, out = git._run_git("branch")
        assert ok is True
        assert out == "main"

    def test_nonzero_returns_false(self, git):
        with patch("subprocess.run", return_value=_make_run_result(1, stdout="")) as _:
            ok, out = git._run_git("status")
        assert ok is False

    def test_git_not_found_returns_false(self, git):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            ok, out = git._run_git("status")
        assert ok is False
        assert "not found" in out

    def test_timeout_returns_false_with_message(self, git):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["git"], 30)):
            ok, out = git._run_git("fetch", "origin")
        assert ok is False
        assert "timed out" in out


class TestBranchExists:
    def test_branch_found_in_list(self, git):
        branch_output = "  main\n* feature/123\n  remotes/origin/feature/456"
        with patch("subprocess.run", return_value=_make_run_result(0, stdout=branch_output)):
            assert git.branch_exists("feature/123") is True

    def test_remote_branch_found(self, git):
        branch_output = "  main\n  remotes/origin/feature/789"
        with patch("subprocess.run", return_value=_make_run_result(0, stdout=branch_output)):
            assert git.branch_exists("feature/789") is True

    def test_branch_not_found(self, git):
        branch_output = "  main\n  develop"
        with patch("subprocess.run", return_value=_make_run_result(0, stdout=branch_output)):
            assert git.branch_exists("feature/999") is False


class TestCheckoutAndPull:
    def test_success_returns_true(self, git):
        with patch.object(git, "_run_git", return_value=(True, "")) as mock:
            result = git.checkout_and_pull("main")
        assert result is True

    def test_checkout_failure_returns_false(self, git):
        def side_effect(*args, **kwargs):
            if args[0] == "checkout":
                return (False, "error")
            return (True, "")
        with patch.object(git, "_run_git", side_effect=side_effect):
            result = git.checkout_and_pull("main")
        assert result is False
