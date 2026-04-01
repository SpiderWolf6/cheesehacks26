"""Shared schemas for agent input/output per architecture.md.

These Pydantic models define the structured output format that all dev and QA
agents must return. The orchestrator validates agent output against these schemas
before applying changes to the project.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FileAction(str, Enum):
    CREATE = "create"
    MODIFY = "modify"


class FileChange(BaseModel):
    """A single file create or modify action from an agent."""

    path: str
    content: str
    action: FileAction = FileAction.CREATE


class ProposalType(str, Enum):
    DEVIATION = "DEVIATION"
    CONCERN = "CONCERN"
    CONFLICT = "CONFLICT"


class Proposal(BaseModel):
    """Cross-agent communication per architecture.md proposals system."""

    type: ProposalType
    summary: str
    impact: str = ""
    affects: str = ""  # Which other agent/domain is affected
    action: str = ""   # Recommended action for PL


class AgentOutput(BaseModel):
    """Structured output returned by dev agents per architecture.md.

    Dev agents return this JSON and never write files directly.
    The orchestrator validates and applies the output.
    """

    files: list[FileChange] = Field(default_factory=list)
    sprint_update: str = ""       # "DONE — ..." or "BLOCKED — ..."
    log_update: str = ""          # Append to {agent}_log.md
    state_additions: list[str] = Field(default_factory=list)  # Append to project_state.md
    proposals: list[Proposal] = Field(default_factory=list)


class QAOutput(BaseModel):
    """Structured output returned by the QA agent per architecture.md."""

    test_files: list[FileChange] = Field(default_factory=list)
    test_command: str = ""
    sprint_update: str = ""
    log_update: str = ""
    proposals: list[Proposal] = Field(default_factory=list)


def parse_agent_output(raw_json: dict[str, Any]) -> AgentOutput:
    """Parse and validate raw JSON dict into an AgentOutput.

    Tolerant of missing fields — fills defaults.
    """
    return AgentOutput.model_validate(raw_json)


def parse_qa_output(raw_json: dict[str, Any]) -> QAOutput:
    """Parse and validate raw JSON dict into a QAOutput."""
    return QAOutput.model_validate(raw_json)
