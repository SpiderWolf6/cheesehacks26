"""Application configuration for AgileGPT.

This module loads environment variables from a local .env file and validates
that required keys exist before the app starts.
"""

from __future__ import annotations

import os
from typing import Dict, List

from dotenv import load_dotenv


class Config:
    """Simple configuration object used across the backend.

    The goal is clarity: read values once, keep them as attributes,
    and fail early if required settings are missing.
    """

    # Azure OpenAI API version used across all deployments.
    AZURE_API_VERSION = "2025-01-01-preview"

    def __init__(self) -> None:
        load_dotenv()

        # Azure OpenAI credentials.
        self.AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")

        # Azure deployment URLs, built from the base endpoint.
        self.AZURE_OPENAI_DEPLOYMENT_41: str = self._deployment_url("gpt-4.1")
        self.AZURE_OPENAI_DEPLOYMENT_41_MINI: str = self._deployment_url("gpt-4.1-mini")
        # self.AZURE_OPENAI_DEPLOYMENT_GPT5_CODEX: str = self._deployment_url("gpt-5-codex")
        # self.AZURE_OPENAI_DEPLOYMENT_O3: str = self._deployment_url("o3")
        # self.AZURE_OPENAI_DEPLOYMENT_GPT5: str = self._deployment_url("gpt-5")

        # Legacy OpenAI (replaced by Azure above).
        # self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        # self.OPENAI_MODEL_CODEX: str = "gpt-5-codex"
        # self.OPENAI_MODEL_41: str = "gpt-4.1"
        # self.OPENAI_MODEL_O3: str = "o3"
        # self.OPEN_MODEL_51: str = "gpt-5.1"

        self.JIRA_BASE_URL: str = os.getenv("JIRA_BASE_URL", "")
        self.JIRA_EMAIL: str = os.getenv("JIRA_EMAIL", "")
        self.JIRA_API_TOKEN: str = self._get_first_non_empty(["JIRA_API_TOKEN", "JIRA_API_KEY"])

        self.FLASK_ENV: str = os.getenv("FLASK_ENV", "development")

        self._validate_required_settings()

    def _deployment_url(self, deployment_name: str) -> str:
        """Build a full Azure OpenAI chat completions URL for a given deployment."""
        return (
            f"{self.AZURE_OPENAI_ENDPOINT}/openai/deployments/"
            f"{deployment_name}/chat/completions?api-version={self.AZURE_API_VERSION}"
        )

    def _get_first_non_empty(self, keys: List[str]) -> str:
        """Return the first non-empty env var value from a list of keys."""
        for key in keys:
            value = os.getenv(key, "")
            if value.strip():
                return value
        return ""

    def _validate_required_settings(self) -> None:
        """Raise a clear error if required environment variables are missing."""
        required_keys: List[str] = [
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "JIRA_BASE_URL",
            "JIRA_EMAIL",
            "JIRA_API_TOKEN",
        ]

        values: Dict[str, str] = {
            "AZURE_OPENAI_API_KEY": self.AZURE_OPENAI_API_KEY,
            "AZURE_OPENAI_ENDPOINT": self.AZURE_OPENAI_ENDPOINT,
            "JIRA_BASE_URL": self.JIRA_BASE_URL,
            "JIRA_EMAIL": self.JIRA_EMAIL,
            "JIRA_API_TOKEN": self.JIRA_API_TOKEN,
        }

        missing_keys: List[str] = [key for key in required_keys if not values[key]]
        if missing_keys:
            missing = ", ".join(missing_keys)
            raise ValueError(
                f"Missing required environment variables: {missing}. "
                "Copy .env.example to .env and fill in the values."
            )