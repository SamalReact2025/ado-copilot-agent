"""Interactive REPL mode for ado-copilot-agent"""

import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt

from utilities import console_helper
from utilities.app_config import get_config
from utilities.logging_helper import get_logger

logger = get_logger(__name__)
console = Console()

_MODES = ["plan", "develop", "review", "complete"]

_MODE_COLORS = {
    "plan": "green",
    "develop": "yellow",
    "review": "cyan",
    "complete": "magenta",
}


def _get_git_branch(directory: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _short_path(path: str) -> str:
    p = Path(path).resolve()
    try:
        rel = p.relative_to(Path.home())
        return "~/" + str(rel).replace("\\", "/")
    except ValueError:
        parts = str(p).replace("\\", "/").split("/")
        return parts[-1] if parts else str(p)


def _render_prompt_header(directory: str, mode_idx: int, model: str) -> None:
    branch = _get_git_branch(directory)
    short_dir = _short_path(directory)
    active_mode = _MODES[mode_idx]
    color = _MODE_COLORS[active_mode]

    console.print()

    # Directory · branch
    branch_part = f" [dim]· {branch}[/dim]" if branch else ""
    console.print(f"  [bold white]ado-copilot-agent[/bold white]  [dim cyan]{short_dir}[/dim cyan]{branch_part}")

    # Mode selector row
    mode_parts = []
    for i, m in enumerate(_MODES):
        if i == mode_idx:
            c = _MODE_COLORS[m]
            mode_parts.append(f"[bold {c}]● {m}[/bold {c}]")
        else:
            mode_parts.append(f"[dim]{m}[/dim]")
    modes_str = "  ".join(mode_parts)
    console.print(f"  {modes_str}  [dim](↵ empty to cycle)[/dim]")

    # Model · hints row
    console.print(
        f"  [bold magenta]◆ {model}[/bold magenta]"
        f"  [dim]/ help  · q quit[/dim]"
    )

    # Styled input separator
    console.print(f"  [dim]{'─' * 56}[/dim]")


def interactive(
    directory: str = typer.Option(".", "-d", "--directory", help="Working directory"),
    model: str = typer.Option(None, "-m", "--model", help="LLM model to use"),
):
    """
    Interactive REPL — select a mode, type a work item ID, hit Enter.
    """
    cfg = get_config()
    active_model = model or cfg.default_model
    mode_idx = 0

    console.rule("[bold cyan]ado-copilot-agent[/bold cyan]", style="cyan")
    console.print(
        "  [dim]Type a work item ID to run the active mode, or [bold]help[/bold] for commands.[/dim]"
    )

    while True:
        _render_prompt_header(directory, mode_idx, active_model)

        try:
            raw = Prompt.ask(
                f"  [bold {_MODE_COLORS[_MODES[mode_idx]]}]>[/bold {_MODE_COLORS[_MODES[mode_idx]]}]"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [dim]Bye![/dim]\n")
            break

        # Empty input → cycle mode
        if not raw:
            mode_idx = (mode_idx + 1) % len(_MODES)
            continue

        # Quit
        if raw.lower() in ("q", "quit", "exit"):
            console.print("  [dim]Bye![/dim]\n")
            break

        # Help
        if raw.lower() in ("?", "help"):
            console.print()
            console.print("  [bold]Commands[/bold]")
            console.print("  [green]<id>[/green]              Run active mode for work item")
            console.print("  [green]plan <id>[/green]         Generate implementation plan")
            console.print("  [green]develop <id>[/green]      Implement feature branch")
            console.print("  [green]review <id>[/green]       Code review")
            console.print("  [green]complete <id>[/green]     Full lifecycle (plan→develop→review)")
            console.print("  [green]model <name>[/green]      Switch model  (e.g. model gpt-4.1)")
            console.print("  [green]↵ empty[/green]           Cycle mode")
            console.print("  [green]q[/green]                 Quit")
            console.print()
            continue

        # Model switch
        if raw.lower().startswith("model "):
            active_model = raw[6:].strip()
            console_helper.show_success(f"Model → {active_model}")
            continue

        # Parse "mode id" or just "id"
        parts = raw.split(maxsplit=1)
        cmd_mode = _MODES[mode_idx]
        work_item_str: Optional[str] = None

        if len(parts) == 2 and parts[0].lower() in _MODES:
            cmd_mode = parts[0].lower()
            work_item_str = parts[1]
        elif len(parts) == 1:
            work_item_str = parts[0]
        else:
            console_helper.show_error(f"Unrecognised input: {raw!r}. Type 'help' for usage.")
            continue

        try:
            work_item_id = int(work_item_str)
            if work_item_id <= 0:
                raise ValueError("must be positive")
        except ValueError:
            console_helper.show_error(f"Invalid work item ID: {work_item_str!r}  (must be a positive integer)")
            continue

        color = _MODE_COLORS[cmd_mode]
        console.print()
        console.rule(
            f"[bold {color}]{cmd_mode}  #[/bold {color}][bold white]{work_item_id}[/bold white]",
            style=color,
        )

        try:
            if cmd_mode == "plan":
                from commands.plan import plan
                plan(work_item_id=work_item_id, directory=directory, model=active_model)

            elif cmd_mode == "develop":
                from commands.develop import develop
                develop(
                    work_item_id=work_item_id,
                    directory=directory,
                    model=active_model,
                    with_review=False,
                    base_branch=None,
                )

            elif cmd_mode == "review":
                from commands.review import review
                review(
                    work_item_id=work_item_id,
                    directory=directory,
                    model=active_model,
                    output_file=None,
                )

            elif cmd_mode == "complete":
                from commands.complete import complete
                complete(
                    work_item_id=work_item_id,
                    directory=directory,
                    model=active_model,
                )

        except SystemExit:
            # typer.Exit raised inside a sub-command — stay in the REPL
            pass
        except Exception as e:
            console_helper.show_error(str(e))
            logger.exception("REPL error for %s #%d: %s", cmd_mode, work_item_id, e)
