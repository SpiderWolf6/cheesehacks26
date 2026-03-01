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

    def __init__(self) -> None:
        load_dotenv()

        # Azure OpenAI shared connection settings.
        self.AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")

        # Canonical Azure deployment names for model routing.
        self.AZURE_OPENAI_DEPLOYMENT_41: str = self._get_first_non_empty(
            ["AZURE_OPENAI_DEPLOYMENT_41", "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_DEPLOYMENT_4.1"]
        )
        self.AZURE_OPENAI_DEPLOYMENT_41_MINI: str = self._get_first_non_empty(
            ["AZURE_OPENAI_DEPLOYMENT_41_MINI", "AZURE_OPENAI_DEPLOYMENT_4.1_mini"]
        )

        # OpenAI key/model for PM agent (o3).
        self.OPENAI_API_KEY: str = self._get_first_non_empty(["OPENAI_API_KEY", "OPEN_AI_KEY"])
        self.OPENAI_MODEL_O3: str = os.getenv("OPENAI_MODEL_O3", "o3")

        self.JIRA_BASE_URL: str = os.getenv("JIRA_BASE_URL", "")
        self.JIRA_EMAIL: str = os.getenv("JIRA_EMAIL", "")
        self.JIRA_API_TOKEN: str = self._get_first_non_empty(["JIRA_API_TOKEN", "JIRA_API_KEY"])

        self.FLASK_ENV: str = os.getenv("FLASK_ENV", "development")

        self._validate_required_settings()

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
            "AZURE_OPENAI_DEPLOYMENT_41",
            "OPENAI_API_KEY",
            "JIRA_BASE_URL",
            "JIRA_EMAIL",
            "JIRA_API_TOKEN",
        ]

        values: Dict[str, str] = {
            "AZURE_OPENAI_API_KEY": self.AZURE_OPENAI_API_KEY,
            "AZURE_OPENAI_ENDPOINT": self.AZURE_OPENAI_ENDPOINT,
            "AZURE_OPENAI_DEPLOYMENT_41": self.AZURE_OPENAI_DEPLOYMENT_41,
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
            "JIRA_BASE_URL": self.JIRA_BASE_URL,
            "JIRA_EMAIL": self.JIRA_EMAIL,
            "JIRA_API_TOKEN": self.JIRA_API_TOKEN,
        }

        missing_keys: List[str] = [key for key in required_keys if not values[key].strip()]
        if missing_keys:
            missing = ", ".join(missing_keys)
            raise ValueError(
                f"Missing required environment variables: {missing}. "
                "Copy .env.example to .env and fill in the values."
            )
