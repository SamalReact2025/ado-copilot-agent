"""Data models for ado-copilot-agent"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AIPlan:
    """Represents the AI-generated plan for a work item"""
    user_story: str
    technical_implementation: str
    acceptance_criteria: str
    test_paths: str
    raw_content: str
    
    @classmethod
    def parse_from_markdown(cls, content: str) -> "AIPlan":
        """
        Parse plan from markdown content.

        Raises:
            ValueError: if required sections (Technical Implementation,
                        Acceptance Criteria) are missing from the content.
        """
        from utilities.plan_parser import PlanParser

        parsed = PlanParser.parse(content)
        if parsed["missing_required"]:
            raise ValueError(
                f"Plan is missing required sections: {', '.join(parsed['missing_required'])}"
            )
        sections = parsed["sections"]
        return cls(
            user_story=sections.get("User Story", ""),
            technical_implementation=sections.get("Technical Implementation", ""),
            acceptance_criteria=sections.get("Acceptance Criteria", ""),
            test_paths=sections.get("Test Paths", ""),
            raw_content=content,
        )


@dataclass
class WorkItem:
    """Represents an Azure DevOps work item"""
    id: int
    title: str
    description: str
    work_item_type: str  # Task, Bug, Feature, Epic, etc.
    state: str
    assigned_to: Optional[str] = None
    iteration_path: Optional[str] = None
    comments: list = None

    def __post_init__(self):
        if self.comments is None:
            self.comments = []


@dataclass
class AgentConfig:
    """Configuration for an AI agent"""
    name: str
    path: str
    description: str
    purpose: str  # 'planner', 'developer', 'reviewer'
