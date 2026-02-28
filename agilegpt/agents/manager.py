"""
Nonprofit Website Consultant — LangChain backend logic.

All LLM setup, session management, prompt chains, and extraction
live here. app.py imports from this module to keep routing separate.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import SystemMessage
from langchain_community.chat_message_histories import ChatMessageHistory

load_dotenv()

# ---------------------------------------------------------------------------
# Azure OpenAI LLMs
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
    temperature=0,  # Deterministic for structured extraction
)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

CONSULTANT_SYSTEM_PROMPT = """
You are a professional web consultant specializing in building websites for nonprofit organizations.
Your job is to gather ALL the information a developer needs to build a website from scratch — 
treat this conversation like a real client discovery session.

Guide the conversation naturally through these phases IN ORDER. Do not rush — 
be thorough in each phase before moving on:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1 — Organization Overview
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Full legal name of the organization
- Mission statement (in their own words)
- Primary target audience (donors, volunteers, beneficiaries, general public, etc.)
- Overall tone/personality (professional, warm, urgent, inspiring, etc.)
- Key goals of the website (raise donations, recruit volunteers, inform, etc.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2 — Pages Needed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Walk through which pages they want. Common nonprofit pages include:
Home, About Us, Our Team, Programs/Services, Impact/Stories,
Donate, Events, Volunteer, Blog/News, Contact, FAQ, Privacy Policy

For each page they confirm:
- What is the purpose of this page?
- Who is the primary audience visiting this page?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3 — Page Content (go page by page)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For EACH confirmed page, gather:
- Main headline / tagline
- Body copy / text content (ask them to provide it or describe it)
- Call-to-action (button text + where it links)
- Images or media needed (do they have photos? Need stock? Video?)
- Any specific sections or components (stats block, testimonials, team grid, etc.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 4 — Functionality & Features
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Online donation form (one-time and/or recurring?)
- Volunteer sign-up form
- Event calendar
- Newsletter / email list signup
- Blog / news section with comments?
- Member login / portal?
- Multi-language support?
- Accessibility requirements (ADA compliance)?
- Contact forms — what fields?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 5 — Design Preferences
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Do they have an existing logo? Brand colors?
- Preferred color palette or feelings (warm, bold, calm, earthy, etc.)
- Font preferences (modern, traditional, playful, etc.)
- Any websites they like the look/feel of?
- Any design styles to avoid?
- Mobile-first requirements?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 6 — Technical Requirements
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Do they have a domain name already?
- Current hosting setup (or starting fresh)?
- Preferred CMS (WordPress, Webflow, Squarespace, custom, etc.)
- Any third-party integrations needed (Salesforce, Mailchimp, PayPal, Stripe, etc.)
- Who will maintain the site after launch (staff, volunteer, agency)?
- Budget range (optional but helpful)?
- Timeline / launch deadline?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONVERSATION RULES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Ask ONE focused question at a time. Never dump multiple questions at once.
- If an answer is vague, probe deeper: "Can you tell me more about..." or "Do you have any existing content for that?"
- Offer helpful examples when they seem unsure (e.g., "Many nonprofits include a stats block on the homepage — something like '500 meals served daily'. Would that be useful?")
- Periodically summarize what you've gathered: "Great! So far I have: [summary]. Let's move on to..."
- Be warm, encouraging, and professional — they may not be tech-savvy.
- If they go off-topic, gently steer back.
- When all phases are complete, say: "I think I have everything I need! Type 'generate summary' and I'll put together a complete website brief for your developer."

Current date: {current_date}
""".strip()

EXTRACTION_SYSTEM_PROMPT = """
You are a data extraction assistant. You will be given a full conversation transcript
between a web consultant and a nonprofit organization.

Extract all gathered website requirements into the following JSON schema.
If a field was not discussed, use null. Be thorough — pull out specific text,
page names, and features that were mentioned.

Respond ONLY with valid JSON, no markdown, no explanation.

Schema:
{{
  "organization": {{
    "name": "",
    "mission": "",
    "target_audience": "",
    "tone": "",
    "website_goals": []
  }},
  "pages": [
    {{
      "name": "",
      "purpose": "",
      "audience": "",
      "headline": "",
      "body_content": "",
      "cta_text": "",
      "cta_link_destination": "",
      "media_needed": "",
      "special_sections": []
    }}
  ],
  "features": {{
    "donation_form": null,
    "recurring_donations": null,
    "volunteer_signup": null,
    "event_calendar": null,
    "newsletter_signup": null,
    "blog": null,
    "member_portal": null,
    "multilanguage": null,
    "ada_compliance": null,
    "contact_form_fields": [],
    "other": []
  }},
  "design": {{
    "has_existing_logo": null,
    "brand_colors": [],
    "color_preferences": "",
    "font_preferences": "",
    "inspiration_sites": [],
    "styles_to_avoid": "",
    "mobile_first": null
  }},
  "technical": {{
    "has_domain": null,
    "domain_name": "",
    "hosting_situation": "",
    "preferred_cms": "",
    "integrations": [],
    "site_maintainer": "",
    "budget": "",
    "timeline": ""
  }},
  "notes": ""
}}
"""

# ---------------------------------------------------------------------------
# In-memory session store
# (Swap ChatMessageHistory for RedisChatMessageHistory in production)
# ---------------------------------------------------------------------------

_session_store: dict[str, ChatMessageHistory] = {}
_session_metadata: dict[str, dict] = {}


def get_session_history(session_id: str) -> ChatMessageHistory:
    """Return existing history or create a new one."""
    if session_id not in _session_store:
        _session_store[session_id] = ChatMessageHistory()
        _session_metadata[session_id] = {
            "created_at": datetime.utcnow().isoformat(),
            "last_active": datetime.utcnow().isoformat(),
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
        _session_metadata[session_id]["last_active"] = datetime.utcnow().isoformat()
    return _session_metadata.get(session_id, {}).get("message_count", 0)


def delete_session(session_id: str) -> None:
    _session_store.pop(session_id, None)
    _session_metadata.pop(session_id, None)


def list_all_sessions() -> list[dict]:
    return [{"session_id": sid, **meta} for sid, meta in _session_metadata.items()]


# ---------------------------------------------------------------------------
# LCEL chain
# ---------------------------------------------------------------------------

_prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content=CONSULTANT_SYSTEM_PROMPT.replace(
        "{current_date}", datetime.utcnow().strftime("%B %d, %Y")
    )),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

_chain = _prompt | llm

chain_with_history = RunnableWithMessageHistory(
    _chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

# ---------------------------------------------------------------------------
# Public functions called by app.py
# ---------------------------------------------------------------------------

def create_session() -> dict:
    """
    Create a new session, generate an opening greeting, and return:
      { "session_id": str, "greeting": str }
    """
    session_id = str(uuid.uuid4())

    greet_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "The user has just connected. Greet them warmly as a web consultant, "
            "introduce yourself briefly, explain that you'll be gathering everything "
            "needed to build their nonprofit website, and ask for the organization's "
            "name to get started. Keep it to 3-4 sentences max."
        )),
        ("human", "Hello"),
    ])

    greeting_text = (greet_prompt | llm).invoke({}).content

    history = get_session_history(session_id)  # initialises metadata too
    history.add_ai_message(greeting_text)
    _session_metadata[session_id]["message_count"] = 1

    return {"session_id": session_id, "greeting": greeting_text}


def send_message(session_id: str, message: str) -> dict:
    """
    Pass a user message through the consultant chain and return:
      { "session_id": str, "reply": str, "message_count": int }
    """
    result = chain_with_history.invoke(
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
    """Return the conversation as a list of { role, content } dicts."""
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
    Run the extraction LLM over the full conversation and return
    a structured requirements dict.
    Raises ValueError on bad input, json.JSONDecodeError on parse failure.
    """
    history = get_session_history(session_id)

    if not history.messages:
        raise ValueError("No conversation history found for this session.")

    transcript = "\n".join(
        f"{'Consultant' if msg.type == 'ai' else 'Client'}: {msg.content}"
        for msg in history.messages
    )

    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", EXTRACTION_SYSTEM_PROMPT),
        ("human", "Here is the conversation transcript:\n\n{transcript}\n\nExtract the requirements now."),
    ])

    raw = (extraction_prompt | extraction_llm).invoke({"transcript": transcript}).content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw)  # let caller handle JSONDecodeError