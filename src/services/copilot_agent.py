"""Copilot agent service to execute agents"""

import subprocess
import os
import shlex
import time
from pathlib import Path
from typing import Optional
from utilities.console_helper import console
from utilities import console_helper
from utilities.logging_helper import get_logger
from utilities.app_config import get_config
from models import AgentConfig

_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 5  # seconds; doubles each attempt

logger = get_logger(__name__)


class CopilotAgentService:
    """Execute AI agents via Copilot CLI"""
    
    def __init__(self, working_directory: Path, model: Optional[str] = None):
        """
        Initialize service.
        
        Args:
            working_directory: Working directory for agent execution
            model: Optional model parameter (e.g., 'gpt-5-mini', 'gpt-4', etc.)
        """
        _cfg = get_config()
        self.working_directory = Path(working_directory).resolve()
        self.model = model or _cfg.default_model
        self._default_timeout = _cfg.agent_timeout
    
    def _check_copilot_available(self) -> bool:
        """Check if copilot CLI is available"""
        try:
            subprocess.run(
                ["copilot", "--version"],
                capture_output=True,
                check=True,
                timeout=5
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _execute_once(
        self,
        agent: AgentConfig,
        prompt: str,
        timeout: int = 300,
        model: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Execute an agent with given prompt.
        
        Workflow:
        1. Get MCP configuration
        2. Read agent file
        3. Execute copilot CLI with MCP servers
        
        Args:
            agent: AgentConfig object with agent information
            prompt: User prompt/request
            timeout: Timeout in seconds (default: 5 minutes)
            model: Optional model override (e.g., 'gpt-5-mini', 'gpt-4', etc.)
        
        Returns:
            Tuple of (success, output)
        """
        if not self._check_copilot_available():
            console_helper.show_error(
                "Copilot CLI is not available. Please install it first."
            )
            logger.error("Copilot CLI not found; aborting agent execution")
            return False, ""
        
        try:
            # Get MCP configuration
            from .mcp_configuration import McpConfigurationService
            mcp_service = McpConfigurationService(self.working_directory)
            mcp_config = mcp_service.get_mcp_config()
            
            # Execute copilot with streaming output (UTF-8 decoding)
            model_to_use = model or self.model

            # Prepend agent file instructions to the prompt (strip YAML frontmatter)
            final_prompt = prompt
            if agent and agent.path:
                try:
                    agent_content = Path(agent.path).read_text(encoding="utf-8")
                    # Strip --- frontmatter block if present
                    if agent_content.startswith("---"):
                        end = agent_content.find("---", 3)
                        if end != -1:
                            agent_content = agent_content[end + 3:].lstrip()
                    if agent_content:
                        final_prompt = f"{agent_content}\n\n{prompt}"
                except (FileNotFoundError, PermissionError) as e:
                    console_helper.show_warning(f"Could not read agent file '{agent.path}': {e}. Proceeding with base prompt.")
                except Exception as e:
                    console_helper.show_warning(f"Unexpected error reading agent file '{agent.path}': {e}. Proceeding with base prompt.")
                    raise

            cmd = [
                "copilot",
                "--additional-mcp-config", mcp_config,
                "--yolo",
                "--model", model_to_use,
                "--prompt", final_prompt,
            ]

            # Print command for debugging — redact the MCP config value to avoid leaking credentials
            redacted_cmd = []
            skip_next = False
            for arg in cmd:
                if skip_next:
                    redacted_cmd.append("[REDACTED]")
                    skip_next = False
                elif arg == "--additional-mcp-config":
                    redacted_cmd.append(arg)
                    skip_next = True
                else:
                    redacted_cmd.append(str(arg))
            cmd_str = ' '.join(shlex.quote(a) for a in redacted_cmd)
            console_helper.show_model(model_to_use)
            console_helper.show_info(f"Running: {cmd_str}")
            logger.info("Executing copilot command (model=%s, agent=%s)", model_to_use, agent.name if agent else "<none>")

            env = os.environ.copy()
            env.setdefault("PYTHONIOENCODING", "utf-8")

            output_lines: list[str] = []
            error_lines: list[str] = []

            start = time.time()
            with console.status("[bold cyan]Executing agent...", spinner="dots") as status:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=str(self.working_directory),
                    env=env
                )

                try:
                    while True:
                        # Read a chunk of stdout
                        line = proc.stdout.readline() if proc.stdout else ""
                        if line:
                            output_lines.append(line)
                            status.update(f"[bold green]Partial Output:\n{''.join(output_lines)[-800:]}")

                        # Check for timeout
                        if timeout and time.time() - start > timeout:
                            proc.kill()
                            raise subprocess.TimeoutExpired(cmd, timeout)

                        # Exit loop when process ends and buffers drained
                        if proc.poll() is not None and not line:
                            break

                    # Drain remaining stdout/stderr
                    if proc.stdout:
                        output_lines.extend(proc.stdout.read().splitlines(keepends=True))
                    if proc.stderr:
                        error_lines.extend(proc.stderr.read().splitlines(keepends=True))
                finally:
                    if proc.stdout:
                        proc.stdout.close()
                    if proc.stderr:
                        proc.stderr.close()

            stdout_text = "".join(output_lines)
            stderr_text = "".join(error_lines)

            if proc.returncode == 0:
                logger.info("Agent completed successfully (returncode=0, output_len=%d)", len(stdout_text))
                console_helper.show_success(f"Agent completed: {stdout_text}")
                return True, stdout_text
            else:
                logger.warning("Agent failed (returncode=%d): %s", proc.returncode, stderr_text[:500])
                console_helper.show_error(f"Agent failed: {stderr_text}")
                return False, stderr_text
        
        except subprocess.TimeoutExpired:
            logger.error("Agent execution timed out after %ds", timeout)
            console_helper.show_error(
                f"Agent execution timed out after {timeout} seconds"
            )
            return False, ""
        except Exception as e:
            logger.exception("Unexpected error during agent execution: %s", e)
            console_helper.show_error(f"Agent execution failed: {str(e)}")
            return False, str(e)

    def execute_agent(
        self,
        agent: AgentConfig,
        prompt: str,
        timeout: Optional[int] = None,
        model: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Execute an agent with given prompt, retrying up to _MAX_RETRIES times
        on transient failures (timeout or non-zero exit).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        for attempt in range(1, _MAX_RETRIES + 2):  # attempts: 1, 2, 3
            success, output = self._execute_once(agent, prompt, effective_timeout, model)
            if success:
                return True, output
            # Do not retry if CLI is simply unavailable (empty output + first attempt messaging)
            if attempt <= _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning("Retry %d/%d after %ds", attempt, _MAX_RETRIES + 1, delay)
                console_helper.show_warning(
                    f"Agent execution failed (attempt {attempt}/{_MAX_RETRIES + 1}). "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                logger.error("Agent execution failed after %d attempts", _MAX_RETRIES + 1)
                console_helper.show_error(
                    f"Agent execution failed after {_MAX_RETRIES + 1} attempts."
                )
        return False, output
