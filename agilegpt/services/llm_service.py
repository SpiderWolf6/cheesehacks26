"""Minimal Azure OpenAI LLM service wrapper.

Supported model targets:
- openai_codex
- openai_o3
"""

from __future__ import annotations

import json
from typing import Any, Dict
import requests
import time

from config import Config


class LLMService:
    """Thin wrapper around OpenAI chat completions.

    The service is intentionally simple:
    - one input format
    - one output format (plain string)
    - small routing layer for model selection
    """

    def __init__(self, config: Config) -> None:
        self.config = config
    
    def generate(self, system_prompt: str, user_content: str, model_target: str = "gpt-4.1") -> str:
        """Send a chat completion request and return assistant text.

        model_target controls which provider/model is used.
        """
        if model_target == "gpt-4.1":
            return self._generate_openai_chat(
                system_prompt=system_prompt,
                user_content=user_content,
                model_name="gpt-4.1",
            )
        if model_target == "gpt-4.1-mini":
            return self._generate_openai_chat(
                system_prompt=system_prompt,
                user_content=user_content,
                model_name="gpt-4.1-mini",
            )
        if model_target == "gpt-5-codex":
            return self._generate_openai_chat(
                system_prompt=system_prompt,
                user_content=user_content,
                model_name="gpt-5-codex",  # or whichever model you actually want here
            )
        if model_target == "o3":
            return self._generate_openai_chat(
                system_prompt=system_prompt,
                user_content=user_content,
                model_name="o3",
            )
        if model_target == "gpt-5.1":
            return self._generate_openai_chat(
                system_prompt=system_prompt,
                user_content=user_content,
                model_name="gpt-5",
            )

        raise ValueError(f"Unsupported model_target: {model_target}")

    def _generate_openai_chat(
        self,
        system_prompt: str,
        user_content: str,
        model_name: str,
        temperature: float | None = None,
    ) -> str:
        """Call OpenAI chat completions with the selected model."""
        url = "https://api.openai.com/v1/chat/completions"

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.OPENAI_API_KEY}",
        }

        payload: Dict[str, Any] = {
            "model": model_name,
            # "max_completion_tokens": 25000,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        if temperature is not None:
            payload["temperature"] = temperature

        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=300)
            except requests.exceptions.ReadTimeout:
                wait = 60
                print(f"Request timed out. Waiting {wait}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait)
                continue

            # Rate limit — wait a full minute for TPM window to reset
            if response.status_code == 429:
                wait = 60 * (attempt + 1)  # 60s, 120s, 180s, 240s, 300s
                print(f"Rate limited (429). Waiting {wait}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait)
                continue

            if response.status_code >= 400:
                raise requests.HTTPError(
                    f"{response.status_code} error from OpenAI Chat Completions: {response.text}",
                    response=response,
                )

            data: Dict[str, Any] = response.json()
            content = data["choices"][0]["message"]["content"]

            # Reasoning model used entire token budget thinking — bump and retry
            if not content:
                payload["max_completion_tokens"] = payload["max_completion_tokens"] + 8000
                print(f"Empty response (reasoning budget exhausted). Retrying with {payload['max_completion_tokens']} tokens...")
                continue

            return content

        raise RuntimeError(f"OpenAI call failed after {max_retries} retries.")
        # ------------------------------------------------------------------
        # Utility helpers
        # ------------------------------------------------------------------

    def list_models(self) -> list[Dict[str, Any]]:
        """Return the list of models available to the configured API key.

        This mirrors the OpenAI `/v1/models` endpoint and returns the raw
        ``data`` field so callers can inspect model ids, ownership, etc.
        """

        url = "https://api.openai.com/v1/models"
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.OPENAI_API_KEY}",
        }

        response = requests.get(url, headers=headers, timeout=120)
        response.raise_for_status()
        body: Dict[str, Any] = response.json()
        # the OpenAI API returns a top-level `data` list containing models
        return body.get("data", [])
