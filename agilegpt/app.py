"""Flask entrypoint — Nonprofit Profile Extractor & PM Handoff."""

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
# 1. Upload & Extract — Start a new session
# ---------------------------------------------------------------------------

@app.post("/session/new")
def new_session() -> Any:
    """
    Upload a PDF annual report → extract nonprofit profile → start review session.

    Accepts multipart/form-data with field "annual_report" (PDF file).

    Returns:
    {
      "session_id": "string",
      "greeting":   "string",
      "profile":    { ... extracted data ... },
      "questions":  [ ... clarifying questions ... ]
    }
    """
    pdf_file = request.files.get("annual_report")
    if not pdf_file:
        return jsonify({"error": "annual_report PDF file is required."}), 400

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # Step 1: Extract profile from PDF
        rag_result = rag_service.extract_from_annual_report(tmp_path)

        # Step 2: Create review session with extracted data
        session_result = manager.create_session(
            profile=rag_result["profile"],
            questions=rag_result["questions"],
        )

        return jsonify(session_result)

    except Exception as exc:
        return jsonify({"error": f"Failed to process annual report: {exc}"}), 500
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# 2. Chat — Review conversation (edit, add, delete, clarify)
# ---------------------------------------------------------------------------

@app.post("/session/chat")
def session_chat() -> Any:
    """
    Send a message in the review conversation.

    Body: { "session_id": "string", "message": "string" }

    Returns: { "session_id": "string", "reply": "string", "message_count": int }
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    session_id = payload.get("session_id", "")
    message = payload.get("message", "")

    if not session_id or not isinstance(session_id, str):
        return jsonify({"error": "session_id is required."}), 400
    if not message or not message.strip():
        return jsonify({"error": "message must be non-empty."}), 400
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404

    result = manager.send_message(session_id, message)
    return jsonify(result)


# ---------------------------------------------------------------------------
# 3. Get / Update Profile
# ---------------------------------------------------------------------------

@app.get("/session/<session_id>/profile")
def get_profile(session_id: str) -> Any:
    """Return the current extracted profile for a session."""
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404

    return jsonify({
        "session_id": session_id,
        "profile": manager.get_profile(session_id),
    })


@app.patch("/session/<session_id>/profile")
def update_profile(session_id: str) -> Any:
    """
    Update specific fields in the profile.

    Body: { "field_name": "new_value", ... }
    Send null as value to delete a field.

    Returns the updated profile.
    """
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404

    updates = request.get_json(silent=True) or {}
    if not updates:
        return jsonify({"error": "No updates provided."}), 400

    updated_profile = manager.update_profile(session_id, updates)
    return jsonify({
        "session_id": session_id,
        "profile": updated_profile,
    })


# ---------------------------------------------------------------------------
# 4. Confirm & Handoff to PM
# ---------------------------------------------------------------------------

@app.post("/session/<session_id>/confirm")
def confirm_and_handoff(session_id: str) -> Any:
    """
    User confirms the profile is correct.
    Generates the PM-ready context paragraph.

    Returns:
    {
      "session_id":     "string",
      "confirmed_at":   "ISO timestamp",
      "profile":        { ... final profile ... },
      "pm_context":     "string — the paragraph sent to the PM agent"
    }
    """
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404

    # Mark as confirmed
    manager.confirm_profile(session_id)
    profile = manager.get_profile(session_id)

    # Generate PM handoff paragraph
    pm_context = rag_service.build_pm_context(profile)

    return jsonify({
        "session_id": session_id,
        "confirmed_at": datetime.utcnow().isoformat(),
        "profile": profile,
        "pm_context": pm_context,
    })


# ---------------------------------------------------------------------------
# 5. Session management
# ---------------------------------------------------------------------------

@app.get("/session/<session_id>/transcript")
def get_transcript(session_id: str) -> Any:
    """Returns the conversation transcript."""
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404

    return jsonify({
        "session_id": session_id,
        "transcript": manager.get_transcript(session_id),
    })


@app.delete("/session/<session_id>")
def delete_session(session_id: str) -> Any:
    if not manager.session_exists(session_id):
        return jsonify({"error": "Session not found."}), 404
    manager.delete_session(session_id)
    return jsonify({"message": f"Session {session_id} deleted."})


@app.get("/sessions")
def list_sessions() -> Any:
    sessions = manager.list_all_sessions()
    return jsonify({"active_sessions": len(sessions), "sessions": sessions})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)