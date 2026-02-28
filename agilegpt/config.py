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

        self.AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")

        self.JIRA_BASE_URL: str = os.getenv("JIRA_BASE_URL", "")
        self.JIRA_EMAIL: str = os.getenv("JIRA_EMAIL", "")
        self.JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "")

        self.FLASK_ENV: str = os.getenv("FLASK_ENV", "development")

        self._validate_required_settings()

    def _validate_required_settings(self) -> None:
        """Raise a clear error if required environment variables are missing."""
        required_keys: List[str] = [
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT",
            "JIRA_BASE_URL",
            "JIRA_EMAIL",
            "JIRA_API_TOKEN",
        ]

        values: Dict[str, str] = {
            "AZURE_OPENAI_API_KEY": self.AZURE_OPENAI_API_KEY,
            "AZURE_OPENAI_ENDPOINT": self.AZURE_OPENAI_ENDPOINT,
            "AZURE_OPENAI_DEPLOYMENT": self.AZURE_OPENAI_DEPLOYMENT,
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
