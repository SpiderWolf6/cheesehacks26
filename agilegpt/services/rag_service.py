"""
rag_extractor.py — Annual Report → Requirements Pre-filler

Pipeline:
  1. Ingest a PDF annual report and split into sentence-level chunks.
  2. Embed all chunks with sentence-transformers (all-MiniLM-L6-v2).
  3. For each field keyword query, retrieve the top-k most similar chunks
     via cosine similarity.
  4. Pass those chunks + the field description to an LLM that decides
     whether the retrieved text actually answers the question and, if so,
     extracts the value.
  5. Return a partially-filled requirements dict and a set of field keys
     that are still missing (so manager.py knows what to ask the user).

Dependencies (add to requirements.txt):
    sentence-transformers
    PyMuPDF          (fitz)
    numpy
    langchain-openai
    python-dotenv
"""

from __future__ import annotations

import json
import os
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import numpy as np
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from sentence_transformers import SentenceTransformer

load_dotenv()

# ---------------------------------------------------------------------------
# Shared embedding model (loaded once at import time)
# ---------------------------------------------------------------------------

_embedder = SentenceTransformer("all-MiniLM-L6-v2")

# ---------------------------------------------------------------------------
# LLM for relevance judgement + extraction
# ---------------------------------------------------------------------------

_judge_llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    temperature=0,
)

# ---------------------------------------------------------------------------
# Keyword manifest
# ---------------------------------------------------------------------------
# Each entry maps a dot-path key (mirrors the requirements JSON schema in
# manager.py) to a human-readable search query AND a description that tells
# the judge LLM exactly what we are looking for.
# ---------------------------------------------------------------------------

@dataclass
class FieldQuery:
    key: str          # dot-path into the requirements dict, e.g. "organization.name"
    query: str        # semantic search query sent to the embedder
    description: str  # plain-English description sent to the judge LLM
    multi: bool = False  # True → expect a list of values


FIELD_QUERIES: list[FieldQuery] = [
    # ── PHASE 1: Organization Overview ──────────────────────────────────────
    FieldQuery(
        key="organization.name",
        query="full legal name of the organization nonprofit",
        description="The full official/legal name of the nonprofit organization.",
    ),
    FieldQuery(
        key="organization.mission",
        query="mission statement purpose vision of the organization",
        description="The organization's mission statement or stated purpose/vision.",
    ),
    FieldQuery(
        key="organization.target_audience",
        query="who we serve beneficiaries donors volunteers target audience",
        description=(
            "The primary audiences the organization serves or targets: "
            "donors, volunteers, beneficiaries, general public, etc."
        ),
    ),
    FieldQuery(
        key="organization.tone",
        query="brand values personality tone voice inspiring warm professional",
        description=(
            "The organization's communication tone or brand personality "
            "(e.g. warm, professional, urgent, inspiring, community-focused)."
        ),
    ),
    FieldQuery(
        key="organization.website_goals",
        query="website goals online strategy donations volunteers awareness",
        description=(
            "Key goals the organization wants its website to achieve: "
            "raise donations, recruit volunteers, raise awareness, inform, etc."
        ),
        multi=True,
    ),
    # ── PHASE 2 / 3: Pages & Content ────────────────────────────────────────
    FieldQuery(
        key="pages",
        query="programs services events team impact stories news blog",
        description=(
            "Any programs, services, events, team information, impact stories, "
            "or news sections that suggest specific website pages are needed."
        ),
        multi=True,
    ),
    # ── PHASE 4: Features ────────────────────────────────────────────────────
    FieldQuery(
        key="features.donation_form",
        query="donate online donation payment fundraising",
        description="Evidence that the organization accepts or solicits online donations.",
    ),
    FieldQuery(
        key="features.recurring_donations",
        query="monthly recurring giving sustaining donors",
        description="Evidence that recurring / monthly donation programmes exist.",
    ),
    FieldQuery(
        key="features.volunteer_signup",
        query="volunteer sign up join our team get involved",
        description="Evidence that the organization recruits volunteers.",
    ),
    FieldQuery(
        key="features.event_calendar",
        query="upcoming events calendar schedule fundraiser gala",
        description="Evidence that the organization runs events that would need a calendar.",
    ),
    FieldQuery(
        key="features.newsletter_signup",
        query="newsletter email list subscribe updates",
        description="Evidence that the organization sends newsletters or email updates.",
    ),
    FieldQuery(
        key="features.blog",
        query="blog news articles stories updates press",
        description="Evidence of a blog, news section, or regular published content.",
    ),
    FieldQuery(
        key="features.multilanguage",
        query="language translation multilingual Spanish French accessibility",
        description="Evidence that the organization serves non-English-speaking audiences.",
    ),
    FieldQuery(
        key="features.ada_compliance",
        query="accessibility ADA compliance disability inclusive",
        description="Evidence that ADA / accessibility compliance is important to the org.",
    ),
    FieldQuery(
        key="features.other",
        query="integrations Salesforce Mailchimp PayPal Stripe CRM platform",
        description=(
            "Third-party tools or integrations the organization currently uses "
            "that a website would need to connect with."
        ),
        multi=True,
    ),
    # ── PHASE 5: Design ──────────────────────────────────────────────────────
    FieldQuery(
        key="design.brand_colors",
        query="brand colors logo color palette visual identity",
        description="The organization's official brand colors or color palette.",
        multi=True,
    ),
    FieldQuery(
        key="design.has_existing_logo",
        query="logo branding visual identity",
        description="Whether the organization has an existing logo or brand identity.",
    ),
    # ── PHASE 6: Technical ───────────────────────────────────────────────────
    FieldQuery(
        key="technical.has_domain",
        query="website domain URL www online presence",
        description="Whether the organization already has a registered domain name.",
    ),
    FieldQuery(
        key="technical.domain_name",
        query="website URL domain name www",
        description="The organization's current website URL or domain name.",
    ),
    FieldQuery(
        key="technical.integrations",
        query="software tools CRM email platform database technology stack",
        description="Third-party platforms the organization uses (CRM, email, payments, etc.).",
        multi=True,
    ),
    FieldQuery(
        key="technical.timeline",
        query="deadline launch date strategic plan timeline fiscal year",
        description="Any timeline, launch deadline, or strategic planning horizon mentioned.",
    ),
    FieldQuery(
        key="technical.budget",
        query="budget funding technology investment annual expenditure",
        description="Any budget figures relevant to a website or technology project.",
    ),
]

# ---------------------------------------------------------------------------
# PDF ingestion & chunking
# ---------------------------------------------------------------------------

def _extract_pdf_text(pdf_path: str | Path) -> str:
    """Extract all text from a PDF using PyMuPDF."""
    doc = fitz.open(str(pdf_path))
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return "\n".join(pages)


def _chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping word-level chunks.
    chunk_size / overlap are measured in *words*.
    """
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Vector store (in-memory, per-document)
# ---------------------------------------------------------------------------

@dataclass
class DocumentIndex:
    chunks: list[str]
    embeddings: np.ndarray  # shape (N, dim)

    @classmethod
    def build(cls, pdf_path: str | Path, chunk_size: int = 300, overlap: int = 50) -> "DocumentIndex":
        text = _extract_pdf_text(pdf_path)
        chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            raise ValueError(f"No text could be extracted from {pdf_path}")
        embeddings = _embedder.encode(chunks, show_progress_bar=False, convert_to_numpy=True)
        return cls(chunks=chunks, embeddings=embeddings)

    def search(self, query: str, top_k: int = 5) -> list[str]:
        """Return the top_k chunks most similar to the query."""
        q_emb = _embedder.encode([query], convert_to_numpy=True)  # (1, dim)
        # Cosine similarity
        norms_doc = np.linalg.norm(self.embeddings, axis=1, keepdims=True) + 1e-9
        norms_q = np.linalg.norm(q_emb, axis=1, keepdims=True) + 1e-9
        sims = (self.embeddings / norms_doc) @ (q_emb / norms_q).T  # (N, 1)
        sims = sims[:, 0]
        top_indices = np.argsort(sims)[::-1][:top_k]
        return [self.chunks[i] for i in top_indices]


# ---------------------------------------------------------------------------
# Judge LLM prompt
# ---------------------------------------------------------------------------

_JUDGE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        textwrap.dedent("""
            You are an information extraction assistant.
            You will be given:
              1. A FIELD DESCRIPTION — what piece of information we are trying to find.
              2. RETRIEVED PASSAGES — text snippets from a nonprofit annual report that
                 may or may not contain that information.

            Your task:
              a) Decide whether the passages genuinely answer the field description.
              b) If YES → extract the relevant value(s) and respond ONLY with a JSON object:
                    {{"found": true, "value": <extracted value>}}
                 For list fields the value must be a JSON array of strings.
                 For boolean fields (has_logo, has_domain, etc.) use true/false.
              c) If NO or NOT ENOUGH INFO → respond ONLY with:
                    {{"found": false, "value": null}}

            Do NOT include markdown fences. Respond with raw JSON only.
        """).strip(),
    ),
    (
        "human",
        textwrap.dedent("""
            FIELD DESCRIPTION:
            {description}

            RETRIEVED PASSAGES:
            {passages}

            Extract now.
        """).strip(),
    ),
])

_judge_chain = _JUDGE_PROMPT | _judge_llm


def _judge_extraction(description: str, passages: list[str]) -> tuple[bool, Any]:
    """
    Ask the judge LLM whether the passages answer the field.
    Returns (found: bool, value: Any).
    """
    passages_text = "\n---\n".join(passages)
    raw = _judge_chain.invoke(
        {"description": description, "passages": passages_text}
    ).content.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        result = json.loads(raw)
        return bool(result.get("found")), result.get("value")
    except json.JSONDecodeError:
        return False, None


# ---------------------------------------------------------------------------
# dot-path helpers
# ---------------------------------------------------------------------------

def _set_nested(d: dict, dot_key: str, value: Any) -> None:
    """Set a value in a nested dict using a dot-separated key path."""
    parts = dot_key.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


def _get_nested(d: dict, dot_key: str) -> Any:
    parts = dot_key.split(".")
    for part in parts:
        if not isinstance(d, dict):
            return None
        d = d.get(part)
    return d


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def extract_from_annual_report(
    pdf_path: str | Path,
    top_k: int = 5,
) -> dict:
    """
    Run the full RAG extraction pipeline on a PDF annual report.

    Returns
    -------
    {
        "prefilled":       dict,   # Partially-filled requirements schema.
        "found_keys":      list,   # Dot-path keys successfully extracted.
        "missing_keys":    list,   # Dot-path keys not found in the document.
    }
    """
    # 1. Build vector index
    print(f"[RAG] Building index for: {pdf_path}")
    index = DocumentIndex.build(pdf_path)
    print(f"[RAG] Indexed {len(index.chunks)} chunks.")

    prefilled: dict = {}
    found_keys: list[str] = []
    missing_keys: list[str] = []

    # 2. Loop through every field query
    for fq in FIELD_QUERIES:
        print(f"[RAG] Searching for: {fq.key!r}")

        # Retrieve relevant chunks
        passages = index.search(fq.query, top_k=top_k)

        # Judge whether the passages actually answer the question
        found, value = _judge_extraction(fq.description, passages)

        if found and value is not None:
            _set_nested(prefilled, fq.key, value)
            found_keys.append(fq.key)
            print(f"[RAG]   ✓ Found: {str(value)[:80]}")
        else:
            missing_keys.append(fq.key)
            print(f"[RAG]   ✗ Not found.")

    return {
        "prefilled": prefilled,
        "found_keys": found_keys,
        "missing_keys": missing_keys,
    }


# ---------------------------------------------------------------------------
# Human-readable summary of what was / wasn't found (used in system prompt)
# ---------------------------------------------------------------------------

# Maps dot-path keys to short human labels shown to the consultant LLM.
_KEY_LABELS: dict[str, str] = {
    "organization.name":            "Organization name",
    "organization.mission":         "Mission statement",
    "organization.target_audience": "Target audience",
    "organization.tone":            "Brand tone/personality",
    "organization.website_goals":   "Website goals",
    "pages":                        "Relevant programs/content for pages",
    "features.donation_form":       "Online donation form",
    "features.recurring_donations": "Recurring donations",
    "features.volunteer_signup":    "Volunteer sign-up",
    "features.event_calendar":      "Event calendar",
    "features.newsletter_signup":   "Newsletter sign-up",
    "features.blog":                "Blog / news section",
    "features.multilanguage":       "Multi-language support",
    "features.ada_compliance":      "ADA / accessibility compliance",
    "features.other":               "Other feature integrations",
    "design.brand_colors":          "Brand colors",
    "design.has_existing_logo":     "Existing logo",
    "technical.has_domain":         "Existing domain",
    "technical.domain_name":        "Domain name / URL",
    "technical.integrations":       "Third-party integrations",
    "technical.timeline":           "Timeline / deadline",
    "technical.budget":             "Budget",
}


def build_prefill_context_block(rag_result: dict) -> str:
    """
    Return a formatted string block to be injected into the consultant's
    system prompt so it knows what has already been extracted from the
    annual report and what still needs to be gathered.
    """
    prefilled = rag_result["prefilled"]
    found_keys = rag_result["found_keys"]
    missing_keys = rag_result["missing_keys"]

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "PRE-FILLED FROM ANNUAL REPORT",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "The following information was already extracted from the organization's",
        "annual report. DO NOT ask about these fields again — treat them as known.",
        "You may briefly confirm them with the user if they seem ambiguous.",
        "",
    ]

    for key in found_keys:
        label = _KEY_LABELS.get(key, key)
        value = _get_nested(prefilled, key)
        value_str = json.dumps(value) if isinstance(value, (list, dict)) else str(value)
        lines.append(f"  ✓ {label}: {value_str}")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "STILL NEEDS TO BE GATHERED FROM USER",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "Focus your conversation on collecting ONLY these missing fields:",
        "",
    ]

    for key in missing_keys:
        label = _KEY_LABELS.get(key, key)
        lines.append(f"  ✗ {label}")

    lines += [
        "",
        "Keep the conversation efficient — skip what you already know.",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    return "\n".join(lines)