"""Tests for utilities/plan_parser.py"""

import pytest
from utilities.plan_parser import PlanParser

FULL_PLAN = """
# COPILOT PLAN

## User Story
As a developer I want to add a login page.

## Technical Implementation
- Add `LoginController`
- Use JWT tokens

## Acceptance Criteria
- Given a valid user, when they log in, then they get a token

## Test Paths
- Open /login, submit valid credentials, check 200 response
"""

PARTIAL_PLAN_MISSING_AC = """
# COPILOT PLAN

## Technical Implementation
- Add SomeService
"""

EMPTY_PLAN = ""


class TestPlanParserParse:
    def test_full_plan_contains_all_sections(self):
        result = PlanParser.parse(FULL_PLAN)
        assert result["missing_required"] == []
        assert "Technical Implementation" in result["sections"]
        assert "Acceptance Criteria" in result["sections"]
        assert "User Story" in result["sections"]
        assert "Test Paths" in result["sections"]

    def test_partial_plan_reports_missing_acceptance_criteria(self):
        result = PlanParser.parse(PARTIAL_PLAN_MISSING_AC)
        assert "Acceptance Criteria" in result["missing_required"]
        assert "Technical Implementation" in result["found_required"]

    def test_empty_plan_reports_all_missing(self):
        result = PlanParser.parse(EMPTY_PLAN)
        assert set(result["missing_required"]) == {"Technical Implementation", "Acceptance Criteria"}

    def test_raw_content_preserved(self):
        result = PlanParser.parse(FULL_PLAN)
        assert result["raw_content"] == FULL_PLAN

    def test_section_extraction_is_case_insensitive(self):
        content = "## technical implementation\nDo things\n## acceptance criteria\nCheck things"
        result = PlanParser.parse(content)
        assert result["missing_required"] == []


class TestPlanParserValidate:
    def test_full_plan_is_valid(self):
        valid, missing = PlanParser.validate(FULL_PLAN)
        assert valid is True
        assert missing == []

    def test_partial_plan_is_invalid(self):
        valid, missing = PlanParser.validate(PARTIAL_PLAN_MISSING_AC)
        assert valid is False
        assert "Acceptance Criteria" in missing

    def test_empty_plan_is_invalid(self):
        valid, missing = PlanParser.validate(EMPTY_PLAN)
        assert valid is False
        assert len(missing) == 2
