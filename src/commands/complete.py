"""Complete command - executes plan, develop, and review in sequence"""

import typer
from commands.plan import plan
from commands.develop import develop
from commands.review import review
from utilities import console_helper
from utilities.logging_helper import get_logger

logger = get_logger(__name__)


def complete(
    work_item_id: int = typer.Argument(..., help="Azure DevOps work item ID"),
    directory: str = typer.Option(".", "-d", "--directory", help="Working directory"),
    model: str = typer.Option(None, "-m", "--model", help="LLM model to use (e.g., claude-sonnet-4.6, gpt-4.1)"),
    base_branch: str = typer.Option("qa", "-b", "--base-branch", help="Base branch to branch from and sync with (default: qa)")
):
    """
    Complete full lifecycle: plan, develop, and review in sequence.

    Workflow:
    1. Generate implementation plan for the work item
    2. Implement the feature based on the plan
    3. Review the code changes
    """
    console_helper.show_info(f"Starting full lifecycle for work item #{work_item_id}...")
    logger.info("Complete command started: work_item=%d, dir=%s", work_item_id, directory)

    # Step 1: Plan
    console_helper.show_info("Step 1/3: Planning...")
    try:
        plan(work_item_id=work_item_id, directory=directory, model=model)
    except typer.Exit as e:
        if e.exit_code != 0:
            console_helper.show_error("[Step 1/3 FAILED] Planning stage did not complete. Aborting lifecycle.")
            raise typer.Exit(code=1)

    # Step 2: Develop
    console_helper.show_info("Step 2/3: Developing...")
    try:
        develop(
            work_item_id=work_item_id,
            directory=directory,
            with_review=False,
            model=model,
            base_branch=base_branch
        )
    except typer.Exit as e:
        if e.exit_code != 0:
            console_helper.show_error("[Step 2/3 FAILED] Development stage did not complete. Aborting lifecycle.")
            raise typer.Exit(code=1)

    # Step 3: Review
    console_helper.show_info("Step 3/3: Reviewing...")
    try:
        review(work_item_id=work_item_id, directory=directory, model=model)
    except typer.Exit as e:
        if e.exit_code != 0:
            console_helper.show_error("[Step 3/3 FAILED] Review stage did not complete.")
            raise typer.Exit(code=1)

    console_helper.show_success(f"Full lifecycle completed for work item #{work_item_id}!")
