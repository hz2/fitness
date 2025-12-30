"""Configuration management for workout analysis."""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


# load environment variables from .env file
load_dotenv()


@dataclass(frozen=True)
class StravaConfig:
    """Strava API configuration settings."""

    client_id: str
    client_secret: str
    refresh_token: str
    auth_url: str = "https://www.strava.com/oauth/authorize"
    token_url: str = "https://www.strava.com/oauth/token"
    api_base: str = "https://www.strava.com/api/v3"

    @classmethod
    def from_env(cls) -> "StravaConfig":
        """
        Create config from environment variables.
        """
        client_id = os.getenv("STRAVA_CLIENT_ID")
        client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            raise ValueError(
                "Missing required Strava environment variables. "
                "Ensure STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, and "
                "STRAVA_REFRESH_TOKEN are set."
            )

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
        )


@dataclass(frozen=True)
class PathConfig:
    """File path configuration."""

    base_dir: Path
    data_dir: Path
    output_dir: Path
    hugo_data_dir: Path
    hugo_content_dir: Path

    @classmethod
    def default(cls) -> "PathConfig":
        """
        Create default path configuration.
        """
        base = Path(__file__).parent.parent
        return cls(
            base_dir=base,
            data_dir=base / "data",
            output_dir=base / "output",
            hugo_data_dir=base.parent / "site" / "data",
            hugo_content_dir=base.parent / "site" / "content",
        )


@dataclass(frozen=True)
class AppConfig:
    """Application-wide configuration."""

    strava: Optional[StravaConfig]
    paths: PathConfig

    @classmethod
    def load(cls) -> "AppConfig":
        """
        Load full application configuration.
        """
        try:
            strava = StravaConfig.from_env()
        except ValueError:
            strava = None

        return cls(strava=strava, paths=PathConfig.default())
