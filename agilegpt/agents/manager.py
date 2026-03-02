"""
Manager Agent — Nonprofit Profile Review & Handoff

Simplified flow:
  1. Receive extracted profile from rag_service.
  2. Present findings to user for review.
  3. Handle edits (confirm, add, delete, modify).
  4. Ask clarifying questions if the LLM flagged gaps.
  5. Once user confirms, package into a PM-ready context paragraph.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_community.chat_message_histories import ChatMessageHistory

load_dotenv()

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL_41_MINI", "gpt-4.1-mini"),
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.4,
)

# ---------------------------------------------------------------------------
# System prompt for the review conversation
# ---------------------------------------------------------------------------

REVIEW_SYSTEM_PROMPT = """
You are a friendly nonprofit website consultant reviewing extracted data
from a client's annual report. The data has already been extracted and
shown to the user in a structured view.

Your role in this conversation:
1. If the user wants to EDIT something — help them refine it and confirm
   the updated value.
2. If the user wants to ADD information — capture it clearly.
3. If the user wants to DELETE something — confirm and note the removal.
4. If you have CLARIFYING QUESTIONS (listed below) — ask them ONE at a time,
   naturally woven into conversation. Don't dump all questions at once.
5. Once the user says they're happy or confirms everything — let them know
   they can click "Confirm & Send to PM" to finalize.

CLARIFYING QUESTIONS TO ASK (if not yet answered):
{questions_block}

Keep it conversational, warm, and brief. You're not interrogating them —
you're making sure you have a complete picture of their nonprofit for
building their website.

The website will have 4 pages: Home, About Us, and 1-2 more that align
with the nonprofit's work. The user doesn't need to think about design
or technology — just help capture WHO they are, WHAT they do, and what
they want their website to communicate.

NEVER ask about tech stack, hosting, databases, or frameworks.
Ask ONE question at a time.

Current date: {current_date}
""".strip()


# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------

_sessions: dict[str, dict] = {}
# Each session: {
#   "history": ChatMessageHistory,
#   "profile": dict,           # the extracted/edited profile
#   "questions": list[str],    # pending clarifying questions
#   "confirmed": bool,
#   "created_at": str,
#   "message_count": int,
# }


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def session_exists(session_id: str) -> bool:
    return session_id in _sessions


def get_session(session_id: str) -> dict | None:
    return _sessions.get(session_id)


def delete_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def list_all_sessions() -> list[dict]:
    return [
        {
            "session_id": sid,
            "org_name": s["profile"].get("org_name", "Unknown"),
            "created_at": s["created_at"],
            "confirmed": s["confirmed"],
            "message_count": s["message_count"],
        }
        for sid, s in _sessions.items()
    ]


# ---------------------------------------------------------------------------
# Create session
# ---------------------------------------------------------------------------

def create_session(
    profile: dict,
    questions: list[str] | None = None,
) -> dict:
    """
    Create a new review session with extracted profile data.

    Returns { "session_id": str, "greeting": str, "profile": dict, "questions": list }
    """
    session_id = str(uuid.uuid4())
    questions = questions or []

    _sessions[session_id] = {
        "history": ChatMessageHistory(),
        "profile": profile,
        "questions": questions,
        "confirmed": False,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "message_count": 0,
    }

    # Generate a greeting that references what was found
    greeting = _generate_greeting(profile, questions)
    _sessions[session_id]["history"].add_ai_message(greeting)
    _sessions[session_id]["message_count"] = 1

    return {
        "session_id": session_id,
        "greeting": greeting,
        "profile": profile,
        "questions": questions,
    }


def _generate_greeting(profile: dict, questions: list[str]) -> str:
    """Ask the LLM to produce a natural greeting based on what was extracted."""
    org_name = profile.get("org_name", "your organization")
    found_fields = [k for k, v in profile.items() if v and v != [] and v != {}]

    prompt_messages = [
        SystemMessage(content="""You are a warm, friendly nonprofit website consultant.
You just finished reading a client's annual report and extracted key information.
Write a brief, natural greeting (3-5 sentences) that:
- Mentions you've reviewed their annual report
- Names their organization
- Highlights 2-3 key things you learned (mission, programs, etc.)
- Invites them to review the extracted info shown on their screen
  and correct anything that's off or add anything missing
- If there are clarifying questions, mention you have a couple of things to ask

Keep it warm and concise. Don't list every field you found."""),
        HumanMessage(content=json.dumps({
            "org_name": org_name,
            "fields_found": found_fields,
            "has_questions": len(questions) > 0,
            "sample_data": {
                "mission": profile.get("mission", ""),
                "programs_count": len(profile.get("programs", [])),
                "target_audience": profile.get("target_audience", ""),
            }
        })),
    ]

    try:
        return llm.invoke(prompt_messages).content.strip()
    except Exception:
        return (
            f"Hi there! I've finished reviewing the annual report for {org_name}. "
            f"I've pulled out everything I could find — take a look at the profile "
            f"on the right and let me know if anything needs correcting or if "
            f"there's anything I missed!"
        )


# ---------------------------------------------------------------------------
# Chat (review loop)
# ---------------------------------------------------------------------------

def send_message(session_id: str, message: str) -> dict:
    """
    User sends a message in the review conversation.
    Returns { "session_id": str, "reply": str, "message_count": int }
    """
    session = _sessions[session_id]
    history = session["history"]

    # Build question block for system prompt
    pending_qs = session["questions"]
    if pending_qs:
        q_block = "\n".join(f"- {q}" for q in pending_qs)
    else:
        q_block = "(No pending questions — all clarified or not applicable.)"

    system = REVIEW_SYSTEM_PROMPT.replace(
        "{questions_block}", q_block
    ).replace(
        "{current_date}", datetime.now(tz=timezone.utc).strftime("%B %d, %Y")
    )

    # Build full message list
    messages = [SystemMessage(content=system)]
    for msg in history.messages:
        if msg.type == "ai":
            messages.append(AIMessage(content=msg.content))
        else:
            messages.append(HumanMessage(content=msg.content))
    messages.append(HumanMessage(content=message))

    # Get reply
    reply = llm.invoke(messages).content.strip()

    # Store in history
    history.add_user_message(message)
    history.add_ai_message(reply)
    session["message_count"] += 1

    return {
        "session_id": session_id,
        "reply": reply,
        "message_count": session["message_count"],
    }


# ---------------------------------------------------------------------------
# Profile editing
# ---------------------------------------------------------------------------

def update_profile(session_id: str, updates: dict) -> dict:
    """
    Merge updates into the session profile.
    `updates` is a partial dict — only the keys provided are overwritten.
    """
    session = _sessions[session_id]
    profile = session["profile"]

    for key, value in updates.items():
        if value is None:
            # Delete the field
            profile.pop(key, None)
        elif isinstance(value, list) and isinstance(profile.get(key), list):
            # Replace the array entirely
            profile[key] = value
        else:
            profile[key] = value

    return profile


def get_profile(session_id: str) -> dict:
    """Return the current profile for a session."""
    return _sessions[session_id]["profile"]


# ---------------------------------------------------------------------------
# Confirm & handoff
# ---------------------------------------------------------------------------

def confirm_profile(session_id: str) -> None:
    """Mark the profile as user-confirmed."""
    _sessions[session_id]["confirmed"] = True


def is_confirmed(session_id: str) -> bool:
    return _sessions[session_id]["confirmed"]


def get_transcript(session_id: str) -> list[dict]:
    history = _sessions[session_id]["history"]
    return [
        {
            "role": "assistant" if msg.type == "ai" else "user",
            "content": msg.content,
        }
        for msg in history.messages
    ]
