"""CLI entry point for ado-copilot-agent"""

import typer

from utilities.config import load_env_from_home
from commands.plan import plan
from commands.develop import develop
from commands.review import review
from commands.complete import complete
from commands.interactive import interactive

# Load .env from home directory
load_env_from_home()

# Create main app
app = typer.Typer()

# Add commands
app.command(help="Enrich work items with AI-generated implementation plans")(plan)
app.command(help="Implement features based on plans")(develop)
app.command(help="Review code changes before PR merge")(review)
app.command(help="Complete full lifecycle: plan, develop, and review in sequence")(complete)
app.command(help="Interactive REPL — select mode, enter work item ID")(interactive)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    directory: str = typer.Option(".", "-d", "--directory", help="Working directory"),
    model: str = typer.Option(None, "-m", "--model", help="LLM model to use"),
):
    """
    Azure DevOps work item lifecycle automation using GitHub Copilot.
    Run without a sub-command to launch the interactive agent.
    """
    if ctx.invoked_subcommand is None:
        interactive(directory=directory, model=model)


def cli():
    """Entry point for the CLI"""
    app()


if __name__ == "__main__":
    cli()
