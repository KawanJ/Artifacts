"""Configuration and settings management."""
import os
from typing import Optional

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, continue without .env loading
    pass


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        """Initialize settings from environment."""
        self.api_key = os.getenv("ARTIFACTS_API_KEY")
        self.api_base_url = os.getenv(
            "ARTIFACTS_API_BASE_URL",
            "https://api.artifactsmmo.com"
        )
        self.character_name = os.getenv("ARTIFACTS_CHARACTER_NAME", "Boomining")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))

    def validate(self) -> None:
        """Validate that all required settings are present.
        
        Raises:
            ValueError: If required settings are missing.
        """
        if not self.api_key:
            raise ValueError(
                "ARTIFACTS_API_KEY environment variable not set. "
                "Please configure it in GitHub Secrets."
            )

    def __repr__(self) -> str:
        """String representation of settings."""
        return (
            f"Settings("
            f"character_name={self.character_name}, "
            f"api_base_url={self.api_base_url}, "
            f"log_level={self.log_level}, "
            f"max_retries={self.max_retries}, "
            f"request_timeout={self.request_timeout}"
            f")"
        )


# Create a global settings instance
settings = Settings()
