"""Strava API client for fetching activity data."""

import json
import logging
from typing import List, Optional, Iterator
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests

from .config import StravaConfig
from .models import StravaActivity


logger = logging.getLogger(__name__)


class StravaClient:
    """Client for interacting with the Strava API."""

    def __init__(self, config: StravaConfig):
        """
        Initialize Strava client with configuration.
        """
        self._config = config
        self._access_token: Optional[str] = None

    def _refresh_access_token(self) -> str:
        """
        Refresh OAuth access token using refresh token.
        """
        response = requests.post(
            self._config.token_url,
            data={
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret,
                "refresh_token": self._config.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        self._access_token = data["access_token"]
        logger.info("Successfully refreshed Strava access token")
        return self._access_token

    @property
    def access_token(self) -> str:
        """
        Get current access token, refreshing if needed.
        """
        if self._access_token is None:
            self._refresh_access_token()
        return self._access_token

    def _get_headers(self) -> dict:
        """Build authorization headers for API requests."""
        return {"Authorization": f"Bearer {self.access_token}"}

    def fetch_activities_page(self, per_page: int = 100, page: int = 1) -> List[dict]:
        """
        Fetch a single page of activities.
        """
        response = requests.get(
            f"{self._config.api_base}/athlete/activities",
            headers=self._get_headers(),
            params={"per_page": per_page, "page": page},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def fetch_all_activities(self) -> Iterator[StravaActivity]:
        """
        Fetch all activities with automatic pagination.
        """
        page = 1
        while True:
            logger.info(f"Fetching activities page {page}")
            raw_activities = self.fetch_activities_page(per_page=100, page=page)

            if not raw_activities:
                break

            for raw in raw_activities:
                try:
                    yield StravaActivity.from_strava_api(raw)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse activity: {e}")

            page += 1

    def fetch_activity_details(self, activity_id: int) -> dict:
        """
        Fetch detailed data for a specific activity.

        Includes full polyline and other detailed metrics.
        """
        response = requests.get(
            f"{self._config.api_base}/activities/{activity_id}",
            headers=self._get_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def fetch_activity_streams(
        self, activity_id: int, keys: Optional[List[str]] = None
    ) -> dict:
        """
        Fetch time-series data streams for an activity.
        """
        if keys is None:
            keys = ["time", "distance", "heartrate", "cadence", "altitude"]

        response = requests.get(
            f"{self._config.api_base}/activities/{activity_id}/streams",
            headers=self._get_headers(),
            params={"keys": ",".join(keys), "key_by_type": "true"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


def run_oauth_flow(config: StravaConfig, port: int = 8000) -> Optional[str]:
    """
    Run OAuth authorization flow to obtain refresh token.

    Starts a local server to capture the OAuth callback and
    exchanges the authorization code for tokens.
    """
    auth_code: Optional[str] = None

    class CallbackHandler(BaseHTTPRequestHandler):
        """HTTP handler to capture OAuth callback."""

        def do_GET(self):
            nonlocal auth_code
            query = parse_qs(urlparse(self.path).query)

            if "code" in query:
                auth_code = query["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Success! You can close this window.</h1>")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Error: No authorization code received")

        def log_message(self, format, *args):
            pass  # suppress server logs

    redirect_uri = f"http://localhost:{port}/callback"
    auth_url = (
        f"{config.auth_url}?"
        f"client_id={config.client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=read,activity:read_all"
    )

    print(f"\n1. Open this URL in your browser:\n{auth_url}\n")
    print("2. Authorize the application")
    print(f"3. Waiting for callback on port {port}...")

    server = HTTPServer(("localhost", port), CallbackHandler)
    server.handle_request()

    if auth_code:
        print(f"\nReceived authorization code: {auth_code[:10]}...")
        print("Exchanging for tokens...")

        response = requests.post(
            config.token_url,
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": auth_code,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        response.raise_for_status()
        tokens = response.json()

        print("\n" + "=" * 50)
        print("Add this to your .env file:")
        print("=" * 50)
        print(f"STRAVA_REFRESH_TOKEN={tokens['refresh_token']}")
        print("=" * 50)

        return tokens["refresh_token"]

    return None


def save_activities_to_json(activities: List[StravaActivity], filepath: Path) -> None:
    """Save activities to JSON file."""
    data = []
    for activity in activities:
        data.append(
            {
                "id": activity.id,
                "name": activity.name,
                "type": activity.activity_type.value,
                "sport_type": activity.sport_type,
                "date": activity.date.isoformat(),
                "start_time": activity.start_time.isoformat(),
                "distance_miles": activity.distance_miles,
                "distance_meters": activity.distance_meters,
                "moving_time_seconds": activity.moving_time_seconds,
                "moving_time_minutes": activity.moving_time_minutes,
                "elapsed_time_seconds": activity.elapsed_time_seconds,
                "elevation_gain_feet": activity.elevation_gain_feet,
                "elevation_gain_meters": activity.elevation_gain_meters,
                "average_speed_mph": activity.average_speed_mph,
                "max_speed_mph": activity.max_speed_mph,
                "average_heartrate": activity.average_heartrate,
                "max_heartrate": activity.max_heartrate,
                "average_cadence": activity.average_cadence,
                "calories": activity.calories,
                "suffer_score": activity.suffer_score,
                "pace_per_mile": activity.pace_per_mile,
            }
        )

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Saved {len(data)} activities to {filepath}")
