"""Product Owner Agent — transforms requirements into behavioral specs.

Per architecture.md, the PO:
- Is called once immediately after EM (Manager).
- Reads the requirements document (from Manager's confirmed profile).
- Produces specs_doc.md: epics, user stories with acceptance criteria,
  content inventory, non-functional requirements.
- Owns the behavioral contract: what the software does (not how).
"""

from __future__ import annotations

from typing import Dict

from agents.base_agent import BaseAgent
from services.llm_service import LLMService


class POAgent(BaseAgent):
    """Product Owner agent — transforms requirements into structured specs."""

    def __init__(self, llm_service: LLMService) -> None:
        system_prompt = """
You are a senior Product Owner with deep experience translating business requirements into structured behavioral specifications.

Your input is a requirements document from the Engineering Manager (who gathered requirements from the client). Your output is a specs document that downstream agents (Architect, developers, QA) will use as the behavioral contract.

--------------------------------------------------
OUTPUT FORMAT
--------------------------------------------------

You MUST output a markdown document following this exact schema:

# Specs Document

## Epics
- <Epic 1 name>
- <Epic 2 name>
- ...

## User stories

### Epic: <Epic name>

#### US-001: <Story title>
As a <user type>, I want <action> so that <benefit>.

Acceptance criteria:
- Given <context>, when <action>, then <result>.
- Given <context>, when <action>, then <result>.

(Repeat for each story)

## Non-functional requirements
- Performance: <requirements>
- Accessibility: <requirements>
- Browser support: <requirements>

## Out of scope (confirmed)
- <item>
- <item>

## Content inventory
| Page | Section | Status | Notes |
|------|---------|--------|-------|
| <page> | <section> | PROVIDED or PLACEHOLDER | <notes> |

--------------------------------------------------
RULES
--------------------------------------------------

1. Every page/screen from the requirements must have at least one user story.
2. Every user story must have Given/When/Then acceptance criteria.
3. Content marked [PLACEHOLDER] in requirements stays [PLACEHOLDER] — never invent content.
4. Content marked [PROVIDED] must reference the exact provided content.
5. Non-functional requirements must include at minimum: performance, accessibility, browser support.
6. Group stories by epic (feature area).
7. Number stories sequentially: US-001, US-002, etc.
8. Be comprehensive — cover navigation, forms, data display, error states.
9. The Architect and QA agents rely on these specs. Be precise.
""".strip()

        super().__init__(
            name="po_agent",
            system_prompt=system_prompt,
            llm_service=llm_service,
            model_target="gpt-4.1-mini",
        )

    def generate_specs(self, requirements: str) -> str:
        """Generate specs_doc from the Manager's confirmed requirements.

        Args:
            requirements: The confirmed profile/requirements from the Manager agent.

        Returns:
            The specs document as markdown text.
        """
        context = {
            "mode": "specs_generation",
            "requirements_document": requirements,
            "instruction": (
                "Read the requirements document above and produce a complete "
                "specs_doc.md following the schema in your instructions. "
                "Cover every page, feature, and functional requirement."
            ),
        }
        return self.run(context)
