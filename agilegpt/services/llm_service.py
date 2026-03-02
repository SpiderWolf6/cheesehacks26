"""Minimal Azure OpenAI LLM service wrapper.

Supported model targets:
- gpt-4.1
- gpt-4.1-mini
# - gpt-5-codex
# - o3
# - gpt-5.1
"""

from __future__ import annotations

import json
from typing import Any, Dict
import requests
import time

from config import Config


class LLMService:
    """Thin wrapper around Azure OpenAI chat completions.

    The service is intentionally simple:
    - one input format
    - one output format (plain string)
    - small routing layer for model selection
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def generate(self, system_prompt: str, user_content: str, model_target: str = "gpt-4.1") -> str:
        """Send a chat completion request and return assistant text.

        model_target controls which Azure deployment is used.
        """
        if model_target == "gpt-4.1":
            return self._generate_azure(
                system_prompt=system_prompt,
                user_content=user_content,
                url=self.config.AZURE_OPENAI_DEPLOYMENT_41,
            )
        if model_target == "gpt-4.1-mini":
            return self._generate_azure(
                system_prompt=system_prompt,
                user_content=user_content,
                url=self.config.AZURE_OPENAI_DEPLOYMENT_41_MINI,
            )

        # if model_target == "gpt-5-codex":
        #     return self._generate_azure(
        #         system_prompt=system_prompt,
        #         user_content=user_content,
        #         url=self.config.AZURE_OPENAI_DEPLOYMENT_GPT5_CODEX,
        #     )
        # if model_target == "o3":
        #     return self._generate_azure(
        #         system_prompt=system_prompt,
        #         user_content=user_content,
        #         url=self.config.AZURE_OPENAI_DEPLOYMENT_O3,
        #     )
        # if model_target == "gpt-5.1":
        #     return self._generate_azure(
        #         system_prompt=system_prompt,
        #         user_content=user_content,
        #         url=self.config.AZURE_OPENAI_DEPLOYMENT_GPT5,
        #     )

        raise ValueError(f"Unsupported model_target: {model_target}")

    def _generate_azure(
        self,
        system_prompt: str,
        user_content: str,
        url: str,
        temperature: float | None = None,
    ) -> str:
        """Call an Azure OpenAI chat completions deployment."""
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "api-key": self.config.AZURE_OPENAI_API_KEY,
        }

        payload: Dict[str, Any] = {
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
                    f"{response.status_code} error from Azure OpenAI Chat Completions: {response.text}",
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

        raise RuntimeError(f"Azure OpenAI call failed after {max_retries} retries.")

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def list_models(self) -> list[Dict[str, Any]]:
        """Return the list of active Azure deployments."""
        return [
            {
                "id": "gpt-4.1",
                "object": "model",
                "owned_by": "azure",
                "url": self.config.AZURE_OPENAI_DEPLOYMENT_41,
            },
            {
                "id": "gpt-4.1-mini",
                "object": "model",
                "owned_by": "azure",
                "url": self.config.AZURE_OPENAI_DEPLOYMENT_41_MINI,
            },
            # {"id": "gpt-5-codex", "owned_by": "azure", "url": self.config.AZURE_OPENAI_DEPLOYMENT_GPT5_CODEX},
            # {"id": "o3",          "owned_by": "azure", "url": self.config.AZURE_OPENAI_DEPLOYMENT_O3},
            # {"id": "gpt-5.1",     "owned_by": "azure", "url": self.config.AZURE_OPENAI_DEPLOYMENT_GPT5},
        ]