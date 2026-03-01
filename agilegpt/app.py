"""Flask entrypoint for AgileGPT backend."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, request
from flask_cors import CORS
from agents import manager
from services import rag_service

app = Flask(__name__)
CORS(app)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Manager (discovery conversation)
# ---------------------------------------------------------------------------

@app.post("/manager/session/new")
def new_session() -> Any:
    """
    Start a new discovery session.

    Optionally accepts a multipart/form-data POST with an annual report PDF:
      - Field name: "annual_report"  (file upload, PDF)

    If a PDF is provided, it is processed through the RAG pipeline first.
    The manager will then know what was already extracted and only ask
    about the remaining gaps.

    Returns:
    {
      "session_id":   "string",
      "greeting":     "string",
      "prefilled":    { ... } | null,
      "found_keys":   [ ... ] | null,
      "missing_keys": [ ... ] | null
    }
    """
    pdf_file = request.files.get("annual_report")

    prefill_context: str | None = None
    rag_result: dict | None = None

    if pdf_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
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


@app.post("/manager/chat")
def manager_chat() -> Any:
    """
    Send a user message and get the manager's reply.

    Body:
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
        return jsonify({"error": "Session not found. Call /manager/session/new first."}), 404

    result = manager.send_message(session_id, message)
    return jsonify(result)


@app.get("/manager/session/<session_id>/transcript")
def get_transcript(session_id: str) -> Any:
    """Returns the full conversation transcript for a session."""
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404

    return jsonify({
        "session_id": session_id,
        "metadata":   manager.get_metadata(session_id),
        "transcript": manager.get_transcript(session_id),
    })


@app.post("/manager/session/<session_id>/handoff")
def handoff_to_pm(session_id: str) -> Any:
    """
    Finalise the discovery session: extract the structured product brief
    and hand it off to the PM agent.

    This is called when the user types "generate brief" and the manager
    confirms it has everything it needs.

    Returns:
    {
      "session_id":    "string",
      "generated_at":  "ISO timestamp",
      "brief":         { ...structured PM-ready brief... },
      "pm_session_id": "string"   // ID of the PM agent session (once wired up)
    }
    """
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404

    try:
        brief = manager.extract_requirements(session_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse structured brief from AI response."}), 500

    # TODO: wire up PM agent here
    # pm_result = pm_agent.kickoff(brief)
    # pm_session_id = pm_result["session_id"]

    return jsonify({
        "session_id":   session_id,
        "generated_at": datetime.utcnow().isoformat(),
        "brief":        brief,
        "pm_session_id": None,  # placeholder until PM agent is built
    })


@app.delete("/manager/session/<session_id>")
def delete_session(session_id: str) -> Any:
    """Clear a session from memory."""
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404

    manager.delete_session(session_id)
    return jsonify({"message": f"Session {session_id} deleted."})


@app.get("/manager/sessions")
def list_sessions() -> Any:
    """List all active sessions."""
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