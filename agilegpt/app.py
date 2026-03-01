"""Flask entrypoint for AgileGPT backend scaffold."""

from __future__ import annotations

import json
from typing import Any, Dict

from flask import Flask, jsonify, request
from flask_cors import CORS
from orchestrator.engine import Orchestrator
from agents import manager


# Global orchestrator instance for this simple MVP scaffold.
# Request flow (current): API request -> Flask endpoint -> simple response.
# Request flow (future): API request -> Manager agent -> Orchestrator + agents.
orchestrator = Orchestrator()

app = Flask(__name__)
CORS(app)

@app.get("/health")
def health() -> Any:
    """Simple health endpoint to confirm backend is running."""
    return jsonify({"status": "hello from backend"})


@app.post("/chat")
def chat() -> Any:
    """Temporary chat endpoint.

    Expected JSON body:
    {
      "project_id": "string",
      "message": "string"
    }
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    project_id = payload.get("project_id", "")
    message = payload.get("message", "")

    if not isinstance(project_id, str) or not isinstance(message, str):
        return jsonify({"error": "project_id and message must be strings"}), 400

    # TODO: Route message through Manager agent and orchestration flow.
    return jsonify({"project_id": project_id, "echo": message})


# ---------------------------------------------------------------------------
# Consultant chatbot endpoints
# ---------------------------------------------------------------------------

@app.post("/consultant/session/new")
def new_session() -> Any:
    """
    Create a new consultant session and return an opening greeting.
    Call this when a new org starts a conversation.

    Returns:
    {
      "session_id": "string",
      "greeting":   "string"
    }
    """
    result = manager.create_session()
    return jsonify(result)


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
    """
    Returns the full conversation transcript for a session.

    Returns:
    {
      "session_id": "string",
      "metadata":   { "created_at": ..., "last_active": ..., "message_count": ... },
      "transcript": [ { "role": "user"|"assistant", "content": "string" } ]
    }
    """
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

    Call this when the consultant signals it's done or the user
    types 'generate summary'.

    Returns:
    {
      "session_id":   "string",
      "generated_at": "ISO timestamp",
      "requirements": { ... }
    }
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
    """
    Returns transcript + extracted requirements in one call.
    Use this for the final 'export brief' action on the frontend.

    Returns:
    {
      "session_id":    "string",
      "created_at":    "ISO timestamp",
      "message_count": int,
      "transcript":    [ ... ],
      "requirements":  { ... }
    }
    """
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