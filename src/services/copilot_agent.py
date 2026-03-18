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

            import threading
            import sys
            import json as _json

            # ── Animated spinner below each tool-call header ──────────────────
            _DOT_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            _ANSI = {
                "cyan":    "\033[36m", "blue":    "\033[34m",
                "yellow":  "\033[33m", "green":   "\033[32m",
                "magenta": "\033[35m", "red":     "\033[31m",
                "white":   "\033[37m",
            }
            _RST  = "\033[0m"
            _DIM  = "\033[2m"
            _BLD  = "\033[1m"

            class _ToolAnim:
                """
                Prints  ● header\n  then spins on the next line.
                On finish() replaces the spinner line with └ result.
                Works even when ● and └ arrive back-to-back (spinner
                may flash one frame but the output is always correct).
                """
                def __init__(self):
                    self._stop    = threading.Event()
                    self._thread  = None
                    self._color   = ""
                    self._pending = False

                def start(self, color: str, header_rest: str) -> None:
                    self._stop.clear()
                    self._color   = _ANSI.get(color, _ANSI["white"])
                    self._pending = True
                    # Committed header line (always visible immediately)
                    sys.stdout.write(
                        f"{self._color}{_BLD}●{_RST}"
                        f"{self._color}{header_rest}{_RST}\n"
                    )
                    # Prime spinner on the next line, no newline
                    sys.stdout.write(f"  {self._color}{_DOT_FRAMES[0]}{_RST}  ")
                    sys.stdout.flush()
                    self._thread = threading.Thread(target=self._run, daemon=True)
                    self._thread.start()

                def _run(self) -> None:
                    idx = 0
                    while not self._stop.wait(0.08):
                        idx = (idx + 1) % len(_DOT_FRAMES)
                        sys.stdout.write(
                            f"\r  {self._color}{_DOT_FRAMES[idx]}{_RST}  "
                        )
                        sys.stdout.flush()

                def finish(self, snippet: str = "") -> None:
                    self._stop.set()
                    if self._thread:
                        self._thread.join(timeout=0.3)
                    if self._pending:
                        result = f"└ {snippet}" if snippet else "└ done"
                        # Erase spinner line, write result
                        sys.stdout.write(f"\r  \033[2K{_DIM}{result}{_RST}\n")
                        sys.stdout.flush()
                        self._pending = False

                def is_active(self) -> bool:
                    return self._pending

            _tool_anim = _ToolAnim()

            # ── Tool name → (color, display label) ───────────────────────────
            _TOOL_META = {
                "read_file":           ("cyan",    "Read"),
                "readFile":            ("cyan",    "Read"),
                "read_text_file":      ("cyan",    "Read Text File"),
                "write_file":          ("yellow",  "Write"),
                "writeFile":           ("yellow",  "Write"),
                "create_file":         ("yellow",  "Create File"),
                "edit_file":           ("yellow",  "Edit File"),
                "list_directory":      ("blue",    "List Directory"),
                "listDirectory":       ("blue",    "List Directory"),
                "search_files":        ("magenta", "Search Files"),
                "searchFiles":         ("magenta", "Search Files"),
                "search_code":         ("magenta", "Search Code"),
                "create_directory":    ("green",   "Create Directory"),
                "delete_file":         ("red",     "Delete"),
                "run_command":         ("yellow",  "Run Command"),
                "get_work_item":       ("cyan",    "Get Work Item"),
                "create_comment":      ("green",   "Create Comment"),
                "update_work_item":    ("green",   "Update Work Item"),
                "create_pull_request": ("green",   "Create PR"),
                "get_pull_request":    ("cyan",    "Get PR"),
            }
            _VERB_COLOR = {
                "read": "cyan",   "get": "cyan",
                "list": "blue",   "search": "magenta",
                "write": "yellow","run": "yellow",   "edit": "yellow",
                "create": "green","update": "green",
                "delete": "red",
            }

            def _fmt_val(v, n: int = 80) -> str:
                s = str(v).replace("\n", "\\n")
                return s if len(s) <= n else s[:n] + "…"

            def _render_line(raw: str) -> None:
                raw = raw.rstrip()
                if not raw:
                    return

                # ── JSON (MCP protocol events) ────────────────────────────────
                obj = None
                try:
                    obj = _json.loads(raw)
                except Exception:
                    pass

                if isinstance(obj, dict):
                    kind = (obj.get("type") or obj.get("event") or "").lower()
                    if kind in ("tool_call", "tool_use", "function_call") or (
                        "tool" in obj or "function" in obj
                    ):
                        tool = (
                            obj.get("tool")
                            or (obj.get("function") or {}).get("name", "")
                            or obj.get("name", "")
                        )
                        args = obj.get("arguments") or obj.get("input") or obj.get("args") or {}
                        if isinstance(args, str):
                            try: args = _json.loads(args)
                            except Exception: pass
                        color, label = _TOOL_META.get(tool, ("white", tool))
                        inline = next(
                            (_fmt_val(args[k], 60) for k in
                             ("path", "file_path", "query", "command", "id", "content")
                             if k in (args or {})), ""
                        )
                        if _tool_anim.is_active():
                            _tool_anim.finish()
                        _tool_anim.start(color, f" {label}  {inline}")
                        return

                    if kind in ("tool_result", "function_result") or "content" in obj:
                        content = obj.get("content") or obj.get("output") or obj.get("result") or ""
                        if isinstance(content, list):
                            content = " ".join(
                                c.get("text", "") if isinstance(c, dict) else str(c)
                                for c in content
                            )
                        _tool_anim.finish(_fmt_val(str(content), 120))
                        return

                    if kind in ("message", "text", "assistant_message"):
                        text = obj.get("text") or obj.get("content") or obj.get("message") or raw
                        if isinstance(text, list):
                            text = " ".join(
                                t.get("text", "") if isinstance(t, dict) else str(t) for t in text
                            )
                        if _tool_anim.is_active():
                            _tool_anim.finish()
                        sys.stdout.write(f"{text}\n"); sys.stdout.flush()
                        return

                # ── Plain-text lines emitted by the copilot CLI ───────────────
                stripped = raw.lstrip()

                # Tool header: "● Verb  path/detail"
                if stripped.startswith("●"):
                    rest = stripped[1:]
                    verb = rest.lstrip().split()[0].lower() if rest.strip() else ""
                    color = next((v for k, v in _VERB_COLOR.items() if verb.startswith(k)), "white")
                    if _tool_anim.is_active():
                        _tool_anim.finish()
                    _tool_anim.start(color, rest)
                    return

                # Result line: "  └ ..." or "  ├ ..."
                if stripped.startswith("└") or stripped.startswith("├"):
                    _tool_anim.finish(stripped[1:].strip())
                    return

                # Anything else (assistant reasoning, status text, etc.)
                if _tool_anim.is_active():
                    _tool_anim.finish()
                sys.stdout.write(f"{raw}\n")
                sys.stdout.flush()
            # ─────────────────────────────────────────────────────────────────

            start = time.time()
            _dot_frames = ["   ", ".  ", ".. ", "..."]
            _stop_anim = threading.Event()
            _has_output = threading.Event()

            def _animate() -> None:
                idx = 0
                while not _stop_anim.wait(timeout=0.4):
                    if _has_output.is_set():
                        break
                    idx = (idx + 1) % len(_dot_frames)
                    elapsed = int(time.time() - start)
                    line = (
                        f"\r  \033[35m◆ {model_to_use}\033[0m "
                        f"\033[36mthinking\033[0m\033[36m{_dot_frames[idx]}\033[0m"
                        f"  \033[2m{elapsed}s\033[0m   "
                    )
                    sys.stdout.write(line)
                    sys.stdout.flush()
                sys.stdout.write("\r" + " " * 72 + "\r")
                sys.stdout.flush()

            anim_thread = threading.Thread(target=_animate, daemon=True)
            anim_thread.start()

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
                    line = proc.stdout.readline() if proc.stdout else ""
                    if line:
                        if not _has_output.is_set():
                            _has_output.set()
                            anim_thread.join(timeout=0.5)
                        output_lines.append(line)
                        _render_line(line)

                    if timeout and time.time() - start > timeout:
                        proc.kill()
                        raise subprocess.TimeoutExpired(cmd, timeout)

                    if proc.poll() is not None and not line:
                        break

                if proc.stdout:
                    output_lines.extend(proc.stdout.read().splitlines(keepends=True))
                if proc.stderr:
                    error_lines.extend(proc.stderr.read().splitlines(keepends=True))
            finally:
                _stop_anim.set()
                anim_thread.join(timeout=1)
                # Finalize any in-flight tool animation
                if _tool_anim.is_active():
                    _tool_anim.finish()
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
