"""Minimal Azure OpenAI chat completion service wrapper."""

from __future__ import annotations

from typing import Any, Dict

import requests

from config import Config


class LLMService:
    """Thin wrapper around Azure OpenAI chat completions.

    This class intentionally stays small and readable.
    It sends a single request and returns a plain text response.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def generate(self, system_prompt: str, user_content: str) -> str:
        """Send a chat completion request and return the assistant message text."""
        endpoint = self.config.AZURE_OPENAI_ENDPOINT.rstrip("/")
        deployment = self.config.AZURE_OPENAI_DEPLOYMENT

        url = (
            f"{endpoint}/openai/deployments/{deployment}/chat/completions"
            "?api-version=2024-02-15-preview"
        )

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "api-key": self.config.AZURE_OPENAI_API_KEY,
        }

        payload: Dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
        }

        # We keep timeout explicit so requests do not hang forever.
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        data: Dict[str, Any] = response.json()
        return data["choices"][0]["message"]["content"]
