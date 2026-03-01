"""Flask entrypoint for AgileGPT backend scaffold."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict

from flask import Flask, jsonify, request
from flask_cors import CORS
from orchestrator.engine import Orchestrator
from agents import manager
from services import rag_service

# Global orchestrator instance for this simple MVP scaffold.
orchestrator = Orchestrator()

app = Flask(__name__)
CORS(app)

@app.get("/health")
def health() -> Any:
    """Simple health endpoint to confirm backend is running."""
    return jsonify({"status": "hello from backend"})


@app.post("/chat")
def chat() -> Any:
    """Temporary chat endpoint."""
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    project_id = payload.get("project_id", "")
    message = payload.get("message", "")

    if not isinstance(project_id, str) or not isinstance(message, str):
        return jsonify({"error": "project_id and message must be strings"}), 400

    return jsonify({"project_id": project_id, "echo": message})


# ---------------------------------------------------------------------------
# Consultant chatbot endpoints
# ---------------------------------------------------------------------------

@app.post("/consultant/session/new")
def new_session() -> Any:
    """
    Create a new consultant session and return an opening greeting.

    Optionally accepts a multipart/form-data POST with an annual report PDF:
      - Field name: "annual_report"  (file upload, PDF)

    If a PDF is provided, it is processed through the RAG pipeline first.
    The consultant will then know what was already extracted and only ask
    about the remaining gaps.

    Returns:
    {
      "session_id":    "string",
      "greeting":      "string",
      "prefilled":     { ... } | null,   // fields extracted from the PDF
      "found_keys":    [ ... ] | null,   // dot-path keys that were found
      "missing_keys":  [ ... ] | null    // dot-path keys still needed
    }
    """
    pdf_file = request.files.get("annual_report")

    prefill_context: str | None = None
    rag_result: dict | None = None

    if pdf_file:
        # Save to a temp file and run RAG extraction
        suffix = ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            pdf_file.save(tmp.name)
            tmp_path = tmp.name

        try:
            rag_result = rag_service.extract_from_annual_report(tmp_path)
            prefill_context = rag_service.build_prefill_context_block(rag_result)
        except Exception as exc:
            return jsonify({"error": f"Failed to process annual report: {exc}"}), 500
        finally:
            os.unlink(tmp_path)

    session_result = manager.create_session(
        prefill_context=prefill_context,
        prefilled_data=rag_result["prefilled"] if rag_result else None,
    )

    return jsonify({
        **session_result,
        "prefilled":    rag_result["prefilled"]   if rag_result else None,
        "found_keys":   rag_result["found_keys"]  if rag_result else None,
        "missing_keys": rag_result["missing_keys"] if rag_result else None,
    })


@app.post("/consultant/chat")
def consultant_chat() -> Any:
    """
    Send a user message to the consultant and receive a reply.

    Expected JSON body:
    {
      "session_id": "string",
      "message":    "string"
    }

    Returns:
    {
      "session_id":    "string",
      "reply":         "string",
      "message_count": int
    }
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    session_id = payload.get("session_id", "")
    message = payload.get("message", "")

    if not isinstance(session_id, str) or not session_id:
        return jsonify({"error": "session_id is required"}), 400
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "message must be a non-empty string"}), 400
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found. Call /consultant/session/new first."}), 404

    result = manager.send_message(session_id, message)
    return jsonify(result)


@app.get("/consultant/session/<session_id>/transcript")
def get_transcript(session_id: str) -> Any:
    """Returns the full conversation transcript for a session."""
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404

    return jsonify({
        "session_id": session_id,
        "metadata": manager.get_metadata(session_id),
        "transcript": manager.get_transcript(session_id),
    })


@app.get("/consultant/session/<session_id>/requirements")
def get_requirements(session_id: str) -> Any:
    """
    Runs the extraction LLM over the conversation and returns a structured
    JSON brief with all gathered website requirements.
    """
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404

    try:
        requirements = manager.extract_requirements(session_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse structured requirements from AI response."}), 500

    from datetime import datetime
    return jsonify({
        "session_id": session_id,
        "generated_at": datetime.utcnow().isoformat(),
        "requirements": requirements,
    })


@app.get("/consultant/session/<session_id>/summary")
def get_full_summary(session_id: str) -> Any:
    """Returns transcript + extracted requirements in one call."""
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404

    try:
        requirements = manager.extract_requirements(session_id)
    except (ValueError, json.JSONDecodeError) as e:
        return jsonify({"error": str(e)}), 500

    meta = manager.get_metadata(session_id)

    return jsonify({
        "session_id": session_id,
        "created_at": meta.get("created_at", ""),
        "message_count": meta.get("message_count", 0),
        "transcript": manager.get_transcript(session_id),
        "requirements": requirements,
    })


@app.delete("/consultant/session/<session_id>")
def delete_session(session_id: str) -> Any:
    """Clear a session from memory."""
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404

    manager.delete_session(session_id)
    return jsonify({"message": f"Session {session_id} deleted."})


@app.get("/consultant/sessions")
def list_sessions() -> Any:
    """List all active sessions (useful for admin/debugging)."""
    sessions = manager.list_all_sessions()
    return jsonify({
        "active_sessions": len(sessions),
        "sessions": sessions,
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)