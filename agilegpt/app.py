"""Flask entrypoint for AgileGPT backend scaffold."""

from __future__ import annotations

from typing import Any, Dict

from flask import Flask, jsonify, request

from orchestrator.engine import Orchestrator


# Global orchestrator instance for this simple MVP scaffold.
# Request flow (current): API request -> Flask endpoint -> simple response.
# Request flow (future): API request -> Manager agent -> Orchestrator + agents.
orchestrator = Orchestrator()

app = Flask(__name__)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
