"""
AgileGPT — Manager Agent

Responsible for conducting a structured discovery conversation with the user
to gather everything needed for the PM agent to spec and build the MVP.

Phases:
  1. Product & Vision
  2. MVP Scope (must-haves + explicit non-goals)
  3. User Flows
  4. Pages (per-page: purpose, audience, sections, CTAs)
  5. Done Criteria

Once complete, extract_requirements() produces a PM-ready brief.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import SystemMessage
from langchain_community.chat_message_histories import ChatMessageHistory

load_dotenv()

# ---------------------------------------------------------------------------
# LLMs
# ---------------------------------------------------------------------------

llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    temperature=0.4,
)

extraction_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    temperature=0,
)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

MANAGER_SYSTEM_PROMPT = """
You are a sharp, empathetic digital consultant specializing in nonprofit websites.
Your job is to have a focused conversation with the user to fully understand what
their website should look and feel like — page by page — so a Product Manager can
plan the build without ever needing to come back to the client for clarification.

You are NOT building the product, and you should NEVER ask technical questions
(no questions about tech stack, databases, frameworks, hosting, etc.).
Instead you are capturing the client's INTENT: what each page should communicate,
what visitors should be able to do, what content already exists, and what the
organization's personality feels like.

{prefill_block}

Guide the conversation through these phases IN ORDER. Skip any fields already
marked as pre-filled above, but feel free to briefly confirm them if something
seems ambiguous.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1 — Who You Are
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Goal: Understand the organization's identity so the PM can set the right tone
across every page.
- Organization name and core mission (what change do you exist to make?)
- Who is the primary audience for the website? (donors, volunteers, people you
  serve, grant-makers, general public — or some mix?)
- What feeling should someone get when they land on the site? Ask for 2-3
  adjectives or reference sites they admire.
- What is the single most important thing the website should accomplish?
  (Drive donations? Recruit volunteers? Educate the public? All of the above
  — but force a #1.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2 — Site Map & Page Deep-Dive
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Goal: Produce a section-level blueprint for every page so the PM can write
tickets without guessing.

Step A — Collect the page list:
  Ask: "If you picture the navigation bar at the top of your site, what links
  would be there?" Probe for anything they might forget (Impact/Results,
  News/Blog, Events, FAQ).

Step B — Deep-dive each page, ONE AT A TIME:
  For every page they named, ask:
  1. "What is the main purpose of this page — what should a visitor
      understand or do after seeing it?"
  2. "Walk me through what someone would see scrolling from top to bottom.
      What sections or blocks of content should be there?"
     (Guide them: hero banner, intro paragraph, stats, image gallery,
      team grid, testimonial, call-to-action strip, etc.)
  3. "What is the main action you want someone to take on this page?"
     (Donate, sign up, read more, contact you, share, etc.)
  4. "Do you already have the text and images for this page, or does it
      need to be written/sourced?"

  Summarize each page back to the user before moving to the next one.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3 — Actions & Visitor Journeys
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Goal: Understand what visitors should be able to DO on the site (beyond
just reading), and what information needs to be collected.

Ask open-endedly first: "Beyond reading about your work, what do you need
visitors to be able to do on the site?" Then probe the details of each
action they mention:

For donations:
  - Should visitors be able to give one-time AND monthly/recurring?
  - Are there set giving levels or suggested amounts?
  - Should they be able to dedicate a gift or add a message?

For volunteer / signup forms:
  - What information do you need to collect? (just name + email, or
    availability, skills, interests, background check consent, etc.)

For events:
  - Do you host regular events? Should visitors RSVP or buy tickets?
  - Or is this more of a simple calendar/list?

For newsletters / email:
  - Just an email capture, or segmented (e.g. donors vs. volunteers)?

For anything else they mention:
  - Who uses it, what should happen when they complete it, and what
    information is collected?

Also ask about:
  - Do you need the site in more than one language?
  - Is accessibility compliance important to your funders or community?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 4 — Look & Feel
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Goal: Give the PM enough design direction to write a creative brief.
- Do you have brand colors? (If yes, what are they? If no, any preferences?)
- Do you have a logo? In what format?
- Are there 1-2 websites (nonprofit or otherwise) whose visual style you
  like? What specifically do you like about them?
- Do you have professional photos of your work, your team, or the people
  you serve — or will we need to plan for stock imagery or illustrations?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 5 — Logistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Goal: Capture practical constraints the PM needs for planning.
- Do you already own a domain name? (If yes, what is it?)
- Do you already use any tools for email, donor management, payments,
  or CRM? (e.g. Mailchimp, Stripe, Salesforce, Blackbaud, PayPal, etc.)
  The PM will figure out how to connect them — just tell me what you use.
- When do you need the site live? Is there a hard deadline (event, grant
  cycle, board meeting)?
- Do you have a budget range in mind? (Totally fine if not — helps the
  PM prioritize.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONVERSATION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Ask ONE focused question at a time. Never dump a list.
2. After completing each page deep-dive, summarize it back:
   "Here's what I have for your [Page Name] page: ... Does that sound right?"
3. After Phase 3, give a quick full-site summary of all pages + actions.
4. Keep the tone conversational, warm, and mindful of nonprofit realities
   (small teams, limited budgets, wearing many hats).
5. NEVER ask about technology, hosting, frameworks, or implementation.
   That's the PM's job.
6. When ALL phases are complete, say:
   "I've got a solid picture of your site! Click **Generate Brief** when
    you're ready, and I'll package everything up for our Product Manager
    to start planning the build."

Current date: {current_date}
""".strip()


EXTRACTION_SYSTEM_PROMPT = """
You are a senior product manager at a web agency. You will be given a conversation
transcript between a nonprofit consultant and a client describing their website needs.

Your job is to extract EVERYTHING discussed into the structured JSON brief below.
This brief is the ONLY artifact the PM agent receives — if something was discussed
but isn't in the brief, it's lost. So be thorough.

Rules:
- Capture what was actually discussed. Do NOT invent information.
- If a field was not discussed, use null (strings), false (booleans), or [] (arrays).
- For page sections, use the names and descriptions the client gave; don't
  over-formalize them.
- Respond ONLY with valid JSON — no markdown, no explanation, no backticks.

Schema:
{
  "organization": {
    "name": null,
    "mission": null,
    "target_audience": null,
    "tone_keywords": [],
    "primary_website_goal": null,
    "secondary_goals": []
  },

  "pages": [
    {
      "name": "Page Name",
      "purpose": "What this page should communicate or accomplish",
      "audience": "Who this page is primarily for",
      "sections": [
        {
          "name": "Section name or type (e.g. Hero Banner, Team Grid, Stats Bar)",
          "description": "What content or message this section contains",
          "content_status": "has_content | needs_writing | needs_images | unknown"
        }
      ],
      "primary_cta": "The main action on this page (e.g. Donate Now, Sign Up)",
      "secondary_ctas": [],
      "notes": "Any extra detail the client mentioned about this page"
    }
  ],

  "navigation": {
    "main_nav_items": [],
    "has_prominent_donate_button": false,
    "notes": null
  },

  "actions": {
    "donations": {
      "needed": false,
      "one_time": false,
      "recurring": false,
      "suggested_amounts": [],
      "dedication_or_message": false,
      "notes": null
    },
    "volunteer_signup": {
      "needed": false,
      "fields_to_collect": [],
      "notes": null
    },
    "events": {
      "needed": false,
      "rsvp_or_tickets": false,
      "notes": null
    },
    "newsletter": {
      "needed": false,
      "segmented": false,
      "notes": null
    },
    "other_actions": [
      {
        "name": "Action name",
        "description": "What it does and who uses it",
        "fields_to_collect": []
      }
    ]
  },

  "design": {
    "brand_colors": [],
    "has_logo": false,
    "logo_format": null,
    "reference_sites": [
      {
        "url": null,
        "what_they_like": null
      }
    ],
    "photo_assets": "has_photos | needs_stock | needs_illustrations | unknown",
    "overall_feel_notes": null
  },

  "accessibility_and_i18n": {
    "multilanguage": false,
    "languages": [],
    "ada_compliance_required": false,
    "notes": null
  },

  "logistics": {
    "has_domain": false,
    "domain_name": null,
    "existing_tools": [],
    "timeline": null,
    "hard_deadline": false,
    "deadline_reason": null,
    "budget_range": null,
    "notes": null
  },

  "content_inventory": {
    "has_existing_website": false,
    "existing_site_url": null,
    "content_ready": "all_ready | partially_ready | needs_writing | unknown",
    "notes": null
  }
}
""".strip()


# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------

_session_store: dict[str, ChatMessageHistory] = {}
_session_metadata: dict[str, dict] = {}
_session_chains: dict[str, RunnableWithMessageHistory] = {}
_session_prefilled: dict[str, dict] = {}


def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in _session_store:
        _session_store[session_id] = ChatMessageHistory()
        _session_metadata[session_id] = {
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "last_active": datetime.now(tz=timezone.utc).isoformat(),
            "message_count": 0,
        }
    return _session_store[session_id]


def session_exists(session_id: str) -> bool:
    return session_id in _session_store


def get_metadata(session_id: str) -> dict:
    return _session_metadata.get(session_id, {})


def increment_message_count(session_id: str) -> int:
    if session_id in _session_metadata:
        _session_metadata[session_id]["message_count"] += 1
        _session_metadata[session_id]["last_active"] = datetime.now(tz=timezone.utc).isoformat()
    return _session_metadata.get(session_id, {}).get("message_count", 0)


def delete_session(session_id: str) -> None:
    _session_store.pop(session_id, None)
    _session_metadata.pop(session_id, None)
    _session_prefilled.pop(session_id, None)
    _session_chains.pop(session_id, None)


def list_all_sessions() -> list[dict]:
    return [{"session_id": sid, **meta} for sid, meta in _session_metadata.items()]


# Default block used when no annual report is provided.
_NO_REPORT_BLOCK = (
    "No annual report was provided. Gather all information from the user "
    "through conversation, covering every phase below — starting from scratch."
)


# ---------------------------------------------------------------------------
# Chain builder
# ---------------------------------------------------------------------------

def _build_chain(prefill_block: str = _NO_REPORT_BLOCK) -> RunnableWithMessageHistory:
    resolved_prompt = MANAGER_SYSTEM_PROMPT.replace(
        "{prefill_block}", prefill_block
    ).replace(
        "{current_date}", datetime.now(tz=timezone.utc).strftime("%B %d, %Y")
    )

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=resolved_prompt),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])

    return RunnableWithMessageHistory(
        prompt | llm,
        get_session_history,
        input_messages_key="input",
        history_messages_key="history",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_session(
    prefill_context: str | None = None,
    prefilled_data: dict | None = None,
) -> dict:
    """
    Create a new discovery session and return an opening greeting.

    Parameters
    ----------
    prefill_context : str, optional
        The formatted context block from rag_service.build_prefill_context_block().
        If provided, the manager skips already-known fields and focuses on gaps.
    prefilled_data : dict, optional
        The raw pre-filled brief dict (rag_result["prefilled"]).
        Stored so extract_requirements() can merge it with conversation data.

    Returns
    -------
    { "session_id": str, "greeting": str }
    """
    session_id = str(uuid.uuid4())

    block = prefill_context if prefill_context else _NO_REPORT_BLOCK
    chain = _build_chain(block)
    _session_chains[session_id] = chain

    if prefilled_data:
        _session_prefilled[session_id] = prefilled_data

    if prefill_context and prefilled_data:
        # Annual report was provided — greet with a summary of what was found
        greet_system = """
You are a friendly nonprofit website consultant who has just read through a
client's annual report before the first call.

Produce the opening message for the session. Keep it warm and natural:
- Greet them and mention you reviewed their annual report.
- Summarize what you already know in a natural way — name the org, mission,
  audience, and any specific details you extracted. Use short bullets.
- Invite them to correct anything that's off.
- Briefly mention what you still need to cover together (don't list every
  missing field — just name the general areas, like "page-by-page details",
  "design preferences", etc.)
- End with a single question to kick things off — don't ask them to confirm,
  just start the conversation naturally.

Do NOT ask multiple questions. Do NOT be overly formal or structured.

PRE-FILLED DATA:
PREFILLED_PLACEHOLDER

PRE-FILL CONTEXT (found vs missing keys):
CONTEXT_PLACEHOLDER
""".strip()

        safe_json = json.dumps(prefilled_data, indent=2).replace("{", "{{").replace("}", "}}")
        safe_ctx  = prefill_context.replace("{", "{{").replace("}", "}}")
        greet_system = greet_system.replace("PREFILLED_PLACEHOLDER", safe_json)
        greet_system = greet_system.replace("CONTEXT_PLACEHOLDER",   safe_ctx)

        greet_prompt = ChatPromptTemplate.from_messages([
            ("system", greet_system),
            ("human", "Hello"),
        ])
        greeting_text = (greet_prompt | llm).invoke({}).content

    else:
        # No annual report — plain intro
        greet_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a friendly nonprofit website consultant starting a new session. "
                "Greet the user warmly, explain in 2-3 sentences that you'll be walking "
                "through a short conversation to understand their organization and what "
                "they need from their website — page by page — so your team's Product "
                "Manager can plan the build. Ask them to start by telling you about their "
                "organization and its mission. Keep it brief and welcoming."
            ),
            ("human", "Hello"),
        ])
        greeting_text = (greet_prompt | llm).invoke({}).content

    history = get_session_history(session_id)
    history.add_ai_message(greeting_text)
    _session_metadata[session_id]["message_count"] = 1

    return {"session_id": session_id, "greeting": greeting_text}


def send_message(session_id: str, message: str) -> dict:
    """
    Pass a user message to the manager chain.

    Returns
    -------
    { "session_id": str, "reply": str, "message_count": int }
    """
    chain = _session_chains.get(session_id)
    if chain is None:
        chain = _build_chain()
        _session_chains[session_id] = chain

    result = chain.invoke(
        {"input": message},
        config={"configurable": {"session_id": session_id}},
    )
    count = increment_message_count(session_id)

    return {
        "session_id": session_id,
        "reply": result.content,
        "message_count": count,
    }


def get_transcript(session_id: str) -> list[dict]:
    history = get_session_history(session_id)
    return [
        {
            "role": "assistant" if msg.type == "ai" else "user",
            "content": msg.content,
        }
        for msg in history.messages
    ]


def extract_requirements(session_id: str) -> dict:
    """
    Run the extraction LLM over the full conversation and return a
    structured PM-ready brief as a dict.
    """
    history = get_session_history(session_id)

    if not history.messages:
        raise ValueError("No conversation history found for this session.")

    transcript = "\n".join(
        f"{'Manager' if msg.type == 'ai' else 'User'}: {msg.content}"
        for msg in history.messages
    )

    prefilled = _session_prefilled.get(session_id, {})
    prefilled_block = (
        f"\n\nPRE-FILLED FROM ANNUAL REPORT (merge these in):\n"
        f"{json.dumps(prefilled, indent=2)}\n"
        if prefilled else ""
    )

    from langchain_core.messages import HumanMessage

    extraction_messages = [
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Here is the full discovery conversation:\n\n{transcript}\n"
            f"{prefilled_block}\n"
            f"Extract the structured product brief now."
        )),
    ]

    raw = extraction_llm.invoke(extraction_messages).content.strip()

    # Strip markdown fences if the model wraps in them anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw)