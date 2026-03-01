"""
rag_service.py — Annual Report → Nonprofit Profile Extractor

Simplified pipeline:
  1. Extract all text from the PDF.
  2. Send the full text to an LLM with a structured extraction prompt.
  3. Return a structured dict of everything learned about the nonprofit.

No embeddings, no vector store — just a single, thorough LLM call.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    temperature=0,
)

# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def _extract_pdf_text(pdf_path: str | Path, max_chars: int = 80_000) -> str:
    """Extract all text from a PDF using PyMuPDF, capped at max_chars."""
    doc = fitz.open(str(pdf_path))
    pages = [page.get_text("text") for page in doc]
    doc.close()
    text = "\n".join(pages)
    return text[:max_chars]


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert at reading nonprofit annual reports and extracting
    structured information. You will receive the full text of a nonprofit's
    annual report.

    Extract EVERYTHING you can find into the JSON schema below.
    - Only include information that is clearly stated or strongly implied.
    - If a field cannot be determined from the report, use null.
    - For arrays, use [] if nothing was found.
    - Be thorough — this data will be used to build their website.

    Also generate a "questions" array: 1-3 clarifying questions about
    important things you COULD NOT determine from the report that would
    be essential for building a website (e.g., preferred tone, specific
    calls to action, what pages they want, etc.).

    Respond ONLY with valid JSON — no markdown, no backticks, no explanation.

    Schema:
    {
      "org_name": "string or null",
      "mission": "string or null — their core mission statement",
      "vision": "string or null — their vision if different from mission",
      "about": "string or null — a paragraph summarizing who they are, their history, what they do",
      "programs": [
        {
          "name": "Program name",
          "description": "What this program does"
        }
      ],
      "impact_stats": [
        {
          "label": "e.g. People Served",
          "value": "e.g. 12,000"
        }
      ],
      "leadership": [
        {
          "name": "Person name",
          "role": "Their title/role"
        }
      ],
      "target_audience": "string or null — who they serve",
      "values": ["list of organizational values"],
      "year_founded": "string or null",
      "location": "string or null — city/state/country",
      "website_url": "string or null — if mentioned",
      "contact_info": "string or null — any address, phone, email found",
      "events": ["list of events or event types mentioned"],
      "partners": ["list of partner organizations mentioned"],
      "financials_summary": "string or null — brief note on revenue, expenses if mentioned",
      "tone_impression": "string or null — your impression of their brand tone from the report (e.g. warm, professional, urgent, community-focused)",
      "suggested_extra_pages": [
        {
          "page_name": "e.g. Our Programs",
          "reason": "Why this page makes sense for them"
        }
      ],
      "questions": [
        "Clarifying question 1",
        "Clarifying question 2"
      ]
    }
""").strip()


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_from_annual_report(pdf_path: str | Path) -> dict:
    """
    Read a PDF annual report and extract structured nonprofit profile data.

    Returns
    -------
    {
        "profile":   dict   — the extracted data (matches schema above),
        "questions": list   — clarifying questions the LLM wants to ask,
        "raw_text_preview": str — first 500 chars of extracted text (for debug)
    }
    """
    print(f"[RAG] Extracting text from: {pdf_path}")
    text = _extract_pdf_text(pdf_path)

    if not text.strip():
        raise ValueError("No text could be extracted from the PDF.")

    print(f"[RAG] Extracted {len(text)} characters. Sending to LLM...")

    messages = [
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=f"Here is the annual report text:\n\n{text}"),
    ]

    raw = _llm.invoke(messages).content.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    profile = json.loads(raw)
    questions = profile.pop("questions", [])

    print(f"[RAG] Extraction complete. Found org: {profile.get('org_name', 'Unknown')}")

    return {
        "profile": profile,
        "questions": questions,
        "raw_text_preview": text[:500],
    }


# ---------------------------------------------------------------------------
# Build PM handoff paragraph
# ---------------------------------------------------------------------------

def build_pm_context(profile: dict) -> str:
    """
    Package the confirmed nonprofit profile into a rich paragraph
    that will be injected into the PM agent's prompt.

    This is the ONLY thing the PM receives, so it must be thorough.
    """
    parts: list[str] = []

    name = profile.get("org_name") or "this nonprofit"
    parts.append(f"The client is {name}.")

    if profile.get("mission"):
        parts.append(f"Their mission: {profile['mission']}")

    if profile.get("vision"):
        parts.append(f"Their vision: {profile['vision']}")

    if profile.get("about"):
        parts.append(f"About them: {profile['about']}")

    if profile.get("year_founded"):
        parts.append(f"Founded: {profile['year_founded']}.")

    if profile.get("location"):
        parts.append(f"Located in {profile['location']}.")

    if profile.get("target_audience"):
        parts.append(f"They primarily serve: {profile['target_audience']}.")

    if profile.get("values"):
        parts.append(f"Core values: {', '.join(profile['values'])}.")

    if profile.get("tone_impression"):
        parts.append(f"Brand tone: {profile['tone_impression']}.")

    if profile.get("programs"):
        prog_strs = [f"  - {p['name']}: {p['description']}" for p in profile["programs"]]
        parts.append("Key programs/services:\n" + "\n".join(prog_strs))

    if profile.get("impact_stats"):
        stat_strs = [f"  - {s['label']}: {s['value']}" for s in profile["impact_stats"]]
        parts.append("Impact stats:\n" + "\n".join(stat_strs))

    if profile.get("leadership"):
        leader_strs = [f"  - {l['name']} ({l['role']})" for l in profile["leadership"]]
        parts.append("Leadership:\n" + "\n".join(leader_strs))

    if profile.get("events"):
        parts.append(f"Events: {', '.join(profile['events'])}.")

    if profile.get("partners"):
        parts.append(f"Partners: {', '.join(profile['partners'])}.")

    if profile.get("financials_summary"):
        parts.append(f"Financials note: {profile['financials_summary']}")

    if profile.get("website_url"):
        parts.append(f"Current website: {profile['website_url']}.")

    if profile.get("contact_info"):
        parts.append(f"Contact: {profile['contact_info']}.")

    if profile.get("suggested_extra_pages"):
        page_strs = [f"  - {p['page_name']}: {p['reason']}" for p in profile["suggested_extra_pages"]]
        parts.append("Suggested website pages beyond Home & About Us:\n" + "\n".join(page_strs))

    return "\n\n".join(parts)