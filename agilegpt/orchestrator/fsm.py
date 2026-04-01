"""Finite State Machine for the AgileGPT pipeline.

Implements the architecture.md FSM with 11 states:
    INIT → EM → PO → ARCHITECT → ENV_SETUP → PL_PLAN
    → SPRINT_N_EXEC → QA_RUN → STATE_UPDATE → PL_REVIEW → DONE

In AgileGPT, the EM state maps to the existing Manager agent
(LangChain chat session). The FSM waits at EM until the manager
session is confirmed, then advances to PO.

The sprint loop (SPRINT_N_EXEC → QA_RUN → STATE_UPDATE → PL_REVIEW)
repeats until all sprints are complete, then transitions to DONE.
"""

from __future__ import annotations

import json
import os
from enum import Enum
from dataclasses import dataclass, field


class FSMState(str, Enum):
    """All possible orchestrator states per architecture.md."""

    INIT = "INIT"
    EM = "EM"
    PO = "PO"
    ARCHITECT = "ARCHITECT"
    ENV_SETUP = "ENV_SETUP"
    PL_PLAN = "PL_PLAN"
    SPRINT_N_EXEC = "SPRINT_N_EXEC"
    QA_RUN = "QA_RUN"
    STATE_UPDATE = "STATE_UPDATE"
    PL_REVIEW = "PL_REVIEW"
    DONE = "DONE"


# Linear planning sequence (before sprint loop)
_PLANNING_SEQUENCE = [
    FSMState.INIT,
    FSMState.EM,
    FSMState.PO,
    FSMState.ARCHITECT,
    FSMState.ENV_SETUP,
    FSMState.PL_PLAN,
]

# Sprint loop sequence (repeats per sprint)
_SPRINT_LOOP = [
    FSMState.SPRINT_N_EXEC,
    FSMState.QA_RUN,
    FSMState.STATE_UPDATE,
    FSMState.PL_REVIEW,
]


@dataclass
class ProjectFSM:
    """Tracks orchestrator progress through the FSM states.

    This is a pure data structure — it does not call agents or perform I/O.
    The orchestrator reads ``current_state`` to decide what to do next, then
    calls ``complete_state()`` when done.
    """

    current_state: FSMState = FSMState.INIT
    current_sprint: int = 0
    total_sprints: int = 0
    completed_states: list[str] = field(default_factory=list)

    # --- State transitions ---------------------------------------------------

    def complete_state(self) -> FSMState:
        """Mark current state as completed and advance to the next state.

        Returns the new current state.
        """
        self.completed_states.append(
            self._state_key(self.current_state, self.current_sprint)
        )
        self.current_state = self._next_state()
        return self.current_state

    def _next_state(self) -> FSMState:
        """Determine the next state based on the FSM transition table."""
        s = self.current_state

        # Planning sequence
        if s in _PLANNING_SEQUENCE:
            idx = _PLANNING_SEQUENCE.index(s)
            if idx + 1 < len(_PLANNING_SEQUENCE):
                return _PLANNING_SEQUENCE[idx + 1]
            # After PL_PLAN, enter sprint loop
            self.current_sprint = 1
            return FSMState.SPRINT_N_EXEC

        # Sprint loop
        if s in _SPRINT_LOOP:
            idx = _SPRINT_LOOP.index(s)
            if idx + 1 < len(_SPRINT_LOOP):
                return _SPRINT_LOOP[idx + 1]
            # End of sprint loop — check if more sprints remain
            if self.current_sprint < self.total_sprints:
                self.current_sprint += 1
                return FSMState.SPRINT_N_EXEC
            return FSMState.DONE

        return FSMState.DONE

    @property
    def is_done(self) -> bool:
        return self.current_state == FSMState.DONE

    @property
    def is_in_sprint_loop(self) -> bool:
        return self.current_state in _SPRINT_LOOP

    def is_state_completed(self, state: FSMState, sprint: int = 0) -> bool:
        """Check if a specific state (optionally for a specific sprint) was completed."""
        return self._state_key(state, sprint) in self.completed_states

    # --- Persistence ----------------------------------------------------------

    _FILENAME = "state.json"

    def save(self, project_path: str) -> None:
        """Write FSM checkpoint to state.json in the project directory."""
        data = {
            "phase": self.current_state.value,
            "sprint": self.current_sprint,
            "total_sprints": self.total_sprints,
            "completed_states": self.completed_states,
        }
        fp = os.path.join(project_path, self._FILENAME)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, project_path: str) -> "ProjectFSM":
        """Resume FSM from state.json. Raises FileNotFoundError if not found."""
        fp = os.path.join(project_path, cls._FILENAME)
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls(
            current_state=FSMState(data["phase"]),
            current_sprint=data.get("sprint", 0),
            total_sprints=data.get("total_sprints", 0),
            completed_states=data.get("completed_states", []),
        )

    # --- Helpers --------------------------------------------------------------

    @staticmethod
    def _state_key(state: FSMState, sprint: int) -> str:
        """Create a unique key for a state, including sprint number for loop states."""
        if state in _SPRINT_LOOP:
            return f"{state.value}_{sprint}"
        return state.value
