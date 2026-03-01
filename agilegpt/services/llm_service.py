"""Minimal multi-provider LLM service wrapper.

Supported model targets:
- openai_o3
- azure_gpt41
- azure_gpt41_mini
"""

from __future__ import annotations

from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

import requests

from config import Config


class LLMService:
    """Thin wrapper around OpenAI + Azure OpenAI chat completions.

    The service is intentionally simple:
    - one input format
    - one output format (plain string)
    - small routing layer for model selection
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def generate(self, system_prompt: str, user_content: str, model_target: str = "azure_gpt41") -> str:
        """Send a chat completion request and return assistant text.

        model_target controls which provider/model is used.
        """
        if model_target == "openai_o3":
            return self._generate_openai_o3(system_prompt, user_content)

        if model_target == "azure_gpt41":
            return self._generate_azure_chat(
                system_prompt=system_prompt,
                user_content=user_content,
                deployment_value=self.config.AZURE_OPENAI_DEPLOYMENT_41,
            )

        if model_target == "azure_gpt41_mini":
            return self._generate_azure_chat(
                system_prompt=system_prompt,
                user_content=user_content,
                deployment_value=self.config.AZURE_OPENAI_DEPLOYMENT_41_MINI,
            )

        raise ValueError(f"Unsupported model_target: {model_target}")

    def _generate_openai_o3(self, system_prompt: str, user_content: str) -> str:
        """Call OpenAI chat completions with the configured o3 model."""
        url = "https://api.openai.com/v1/chat/completions"

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.OPENAI_API_KEY}",
        }

        payload: Dict[str, Any] = {
            "model": self.config.OPENAI_MODEL_O3,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        data: Dict[str, Any] = response.json()
        return data["choices"][0]["message"]["content"]

    def _extract_azure_deployment_name(self, deployment_value: str) -> str:
        """Allow either deployment name or full Azure URL in env values.

        We prefer deployment names, but this helper makes current env files
        backward compatible when a full chat completion URL is provided.
        """
        cleaned = deployment_value.strip()
        if not cleaned:
            return ""

        if "http://" not in cleaned and "https://" not in cleaned:
            return cleaned

        parsed = urlparse(cleaned)
        path_parts = [part for part in parsed.path.split("/") if part]
        if "deployments" in path_parts:
            deployment_index = path_parts.index("deployments")
            if deployment_index + 1 < len(path_parts):
                return path_parts[deployment_index + 1]

        return cleaned

    def _extract_azure_api_version(self, deployment_value: str) -> str:
        """Get API version from Azure URL when present; otherwise use default."""
        parsed = urlparse(deployment_value)
        query = parse_qs(parsed.query)
        api_version_values = query.get("api-version", [])
        if api_version_values and api_version_values[0].strip():
            return api_version_values[0]
        return "2024-02-15-preview"

    def _generate_azure_chat(self, system_prompt: str, user_content: str, deployment_value: str) -> str:
        """Call Azure OpenAI chat completions using selected deployment."""
        endpoint = self.config.AZURE_OPENAI_ENDPOINT.rstrip("/")
        deployment = self._extract_azure_deployment_name(deployment_value)
        api_version = self._extract_azure_api_version(deployment_value)

        url = (
            f"{endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={api_version}"
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
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        data: Dict[str, Any] = response.json()
        return data["choices"][0]["message"]["content"]
