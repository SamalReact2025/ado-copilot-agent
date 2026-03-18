"""Tests for models/__init__.py — AIPlan.parse_from_markdown"""

import pytest
from models import AIPlan

VALID_MARKDOWN = """
# COPILOT PLAN

## User Story
As a user I want X.

## Technical Implementation
- Implement X using pattern Y
- Add class Foo in module bar

## Acceptance Criteria
- Given state A, when action B, then result C

## Test Paths
- Navigate to /feature-x and verify C
"""

MISSING_AC_MARKDOWN = """
## Technical Implementation
- Do something
"""

MISSING_TI_MARKDOWN = """
## Acceptance Criteria
- Something must happen
"""


class TestAIPlanParseFromMarkdown:
    def test_valid_markdown_returns_plan(self):
        plan = AIPlan.parse_from_markdown(VALID_MARKDOWN)
        assert isinstance(plan, AIPlan)
        assert "Implement X" in plan.technical_implementation
        assert "Given state A" in plan.acceptance_criteria
        assert "As a user" in plan.user_story
        assert plan.raw_content == VALID_MARKDOWN

    def test_missing_acceptance_criteria_raises(self):
        with pytest.raises(ValueError, match="Acceptance Criteria"):
            AIPlan.parse_from_markdown(MISSING_AC_MARKDOWN)

    def test_missing_technical_implementation_raises(self):
        with pytest.raises(ValueError, match="Technical Implementation"):
            AIPlan.parse_from_markdown(MISSING_TI_MARKDOWN)

    def test_empty_content_raises(self):
        with pytest.raises(ValueError):
            AIPlan.parse_from_markdown("")

    def test_optional_sections_default_to_empty_string(self):
        # Only required sections present
        content = "## Technical Implementation\nFoo\n## Acceptance Criteria\nBar"
        plan = AIPlan.parse_from_markdown(content)
        assert plan.user_story == ""
        assert plan.test_paths == ""
