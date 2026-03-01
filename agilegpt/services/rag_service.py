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
    key: str
    query: str
    description: str
    multi: bool = False

FIELD_QUERIES: list[FieldQuery] = [
    # ── Organization ─────────────────────────────────────────────────────────
    FieldQuery(key="organization.name", query="organization name nonprofit charity name", description="The official name of the nonprofit organization."),
    FieldQuery(key="organization.mission", query="mission statement purpose what we do goal vision", description="The core mission or vision statement of the organization."),
    FieldQuery(key="organization.target_audience", query="who we serve target audience community beneficiaries", description="The primary people, communities, or causes the organization serves."),
    FieldQuery(key="organization.tone_keywords", query="brand voice tone values personality", description="The brand personality or tone of the organization as a list of keywords (e.g., ['professional', 'compassionate', 'urgent']).", multi=True),
    FieldQuery(key="organization.primary_website_goal", query="website goals digital strategy online objective", description="What the organization hopes to achieve with their website (e.g., increase donations, raise awareness)."),

    # ── Pages / Programs (what an annual report reveals about site structure) ─
    FieldQuery(key="pages", query="programs services initiatives departments what we do", description="Key programs, services, or initiatives that would each need a page or section on the website.", multi=True),

    # ── Actions — Donations ──────────────────────────────────────────────────
    FieldQuery(key="actions.donations.needed", query="donate online donation form give money fundraising", description="Whether the organization accepts or solicits donations (true/false)."),
    FieldQuery(key="actions.donations.recurring", query="monthly giving recurring donations sustainers", description="Whether the organization supports monthly or recurring giving (true/false)."),

    # ── Actions — Volunteers ─────────────────────────────────────────────────
    FieldQuery(key="actions.volunteer_signup.needed", query="volunteer application sign up to help", description="Whether the organization recruits volunteers (true/false)."),

    # ── Actions — Events ─────────────────────────────────────────────────────
    FieldQuery(key="actions.events.needed", query="events calendar upcoming events schedule gala", description="Whether the organization hosts events that would appear on the website (true/false)."),

    # ── Actions — Newsletter ─────────────────────────────────────────────────
    FieldQuery(key="actions.newsletter.needed", query="newsletter email list subscribe updates", description="Whether the organization sends newsletters or email updates (true/false)."),

    # ── Accessibility & i18n ─────────────────────────────────────────────────
    FieldQuery(key="accessibility_and_i18n.multilanguage", query="languages spanish translation multilingual", description="Whether the organization serves communities in multiple languages (true/false)."),
    FieldQuery(key="accessibility_and_i18n.languages", query="spanish english french bilingual language", description="Specific languages used by the organization.", multi=True),
    FieldQuery(key="accessibility_and_i18n.ada_compliance_required", query="accessibility ADA compliance WCAG blind deaf", description="Whether accessibility compliance is explicitly mentioned (true/false)."),

    # ── Design ───────────────────────────────────────────────────────────────
    FieldQuery(key="design.brand_colors", query="brand colors color palette primary colors hex codes", description="The organization's official brand colors.", multi=True),
    FieldQuery(key="design.has_logo", query="logo brand mark visual identity", description="Whether the organization has an existing logo (true/false)."),

    # ── Logistics ────────────────────────────────────────────────────────────
    FieldQuery(key="logistics.has_domain", query="domain name website url existing site", description="Whether the organization already has a website or domain (true/false)."),
    FieldQuery(key="logistics.domain_name", query="domain name url website address .org", description="The specific domain name URL if they have one (e.g., example.org)."),
    FieldQuery(key="logistics.existing_tools", query="CRM integration salesforce mailchimp blackbaud stripe donorperfect", description="Third-party software the organization already uses (e.g., Stripe, Salesforce, Mailchimp).", multi=True),

    # ── Content inventory ────────────────────────────────────────────────────
    FieldQuery(key="content_inventory.has_existing_website", query="current website existing site redesign", description="Whether the organization currently has a website (true/false)."),
    FieldQuery(key="content_inventory.existing_site_url", query="website url current site address", description="The URL of the organization's current website, if any."),
]

_KEY_LABELS: dict[str, str] = {
    "organization.name": "Org Name",
    "organization.mission": "Mission",
    "organization.target_audience": "Target Audience",
    "organization.tone_keywords": "Brand Tone",
    "organization.primary_website_goal": "Website Goal",
    "pages": "Programs / Pages",
    "actions.donations.needed": "Accepts Donations",
    "actions.donations.recurring": "Recurring Giving",
    "actions.volunteer_signup.needed": "Recruits Volunteers",
    "actions.events.needed": "Hosts Events",
    "actions.newsletter.needed": "Sends Newsletter",
    "accessibility_and_i18n.multilanguage": "Multi-language",
    "accessibility_and_i18n.languages": "Languages",
    "accessibility_and_i18n.ada_compliance_required": "ADA Compliance",
    "design.brand_colors": "Brand Colors",
    "design.has_logo": "Has Logo",
    "logistics.has_domain": "Has Domain",
    "logistics.domain_name": "Domain Name",
    "logistics.existing_tools": "Existing Tools",
    "content_inventory.has_existing_website": "Has Existing Site",
    "content_inventory.existing_site_url": "Current Site URL",
}

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
# (Defined once above as _KEY_LABELS — no second definition needed.)


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