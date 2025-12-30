"""
Google Sheets client for fetching workout data.

Provides methods for reading workout data from Google Sheets,
either via API (requires credentials) or from exported TSV/CSV files.
"""

import csv
import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Iterator

from .models import LiftingWorkout, Exercise, CardioSession


logger = logging.getLogger(__name__)


class GoogleSheetsClient:
    """
    Client for fetching data from Google Sheets API.

    Requires either:
    - GOOGLE_SHEETS_CREDENTIALS env var (JSON string)
    - credentials.json file in project root
    """

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

    def __init__(self, sheet_id: Optional[str] = None, range_name: Optional[str] = None):
        """
        Initialize Google Sheets client.

        Parameters:
            sheet_id: Google Sheet ID (from URL). Can also be set via
                      GOOGLE_SHEET_ID environment variable.
            range_name: Sheet name or A1 range. Can also be set via
                        GOOGLE_SHEET_RANGE environment variable.
        """
        self._sheet_id = sheet_id or os.getenv("GOOGLE_SHEET_ID")
        self._range_name = range_name or os.getenv("GOOGLE_SHEET_RANGE", "Sheet1")
        self._service = None

    def _get_credentials(self):
        """
        Get Google credentials from environment or file.

        Returns:
            Google credentials object.

        Raises:
            ValueError: If no credentials are available.
        """
        try:
            from google.oauth2.service_account import Credentials
        except ImportError:
            raise ImportError(
                "google-auth not installed. Run: pip install google-auth google-api-python-client"
            )

        # try environment variable first (for CI/CD)
        creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
        if creds_json:
            try:
                creds_info = json.loads(creds_json)
                return Credentials.from_service_account_info(
                    creds_info, scopes=self.SCOPES
                )
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid GOOGLE_SHEETS_CREDENTIALS JSON: {e}")

        # try local credentials file
        creds_file = Path("credentials.json")
        if creds_file.exists():
            return Credentials.from_service_account_file(
                str(creds_file), scopes=self.SCOPES
            )

        raise ValueError(
            "No Google credentials found. Set GOOGLE_SHEETS_CREDENTIALS env var "
            "or place credentials.json in project root."
        )

    def _get_service(self):
        """
        Get or create Google Sheets API service.

        Returns:
            Google Sheets API service object.
        """
        if self._service is None:
            try:
                from googleapiclient.discovery import build
            except ImportError:
                raise ImportError(
                    "google-api-python-client not installed. "
                    "Run: pip install google-api-python-client"
                )

            creds = self._get_credentials()
            self._service = build("sheets", "v4", credentials=creds)

        return self._service

    def fetch_sheet_data(
        self, range_name: Optional[str] = None, sheet_id: Optional[str] = None
    ) -> List[List[str]]:
        """
        Fetch raw data from a Google Sheet.

        Parameters:
            range_name: Sheet name or A1 range notation (e.g., "Sheet1!A:Z").
                        Defaults to GOOGLE_SHEET_RANGE env var or "Sheet1".
            sheet_id: Override the default sheet ID.

        Returns:
            List of rows, where each row is a list of cell values.

        Raises:
            ValueError: If no sheet ID is configured.
        """
        sid = sheet_id or self._sheet_id
        rng = range_name or self._range_name
        
        if not sid:
            raise ValueError(
                "No sheet ID provided. Set GOOGLE_SHEET_ID env var or pass sheet_id."
            )

        service = self._get_service()
        sheet = service.spreadsheets()

        logger.info(f"Fetching data from Google Sheet: {sid}, range: {rng}")
        result = sheet.values().get(spreadsheetId=sid, range=rng).execute()

        rows = result.get("values", [])
        logger.info(f"Fetched {len(rows)} rows from Google Sheets")
        return rows

    def fetch_workouts(
        self, range_name: Optional[str] = None, sheet_id: Optional[str] = None
    ) -> List[LiftingWorkout]:
        """
        Fetch and parse workout data from Google Sheets.

        Parameters:
            range_name: Sheet name or A1 range notation.
            sheet_id: Override the default sheet ID.

        Returns:
            List of parsed LiftingWorkout objects.
        """
        rows = self.fetch_sheet_data(range_name, sheet_id)
        if not rows:
            logger.warning("No data found in Google Sheet")
            return []

        # parse using the same logic as file parser
        parser = GoogleSheetDataParser(rows)
        workouts = list(parser.parse())
        logger.info(f"Parsed {len(workouts)} workouts from Google Sheets")
        return workouts

    @staticmethod
    def is_available() -> bool:
        """
        Check if Google Sheets API credentials are available.

        Returns:
            True if credentials are configured, False otherwise.
        """
        if os.getenv("GOOGLE_SHEETS_CREDENTIALS"):
            return True
        if Path("credentials.json").exists():
            return True
        return False


class GoogleSheetDataParser:
    """
    Parser for workout data fetched from Google Sheets API.

    Uses the same parsing logic as WorkoutSheetParser but operates
    on in-memory data rather than files.
    """

    DATE_COLUMN = "date"
    MUSCLE_GROUP_COLUMN = "muscle group(s)"
    CARDIO_COLUMN = "cardio"
    PUSHUPS_COLUMN = "push-ups"
    PULLUPS_COLUMN = "pull-ups"
    WEIGHT_COLUMN = "weight"
    MEMO_COLUMN = "memo"

    def __init__(self, rows: List[List[str]]):
        """
        Initialize parser with row data.

        Parameters:
            rows: List of rows from Google Sheets API.
        """
        self._rows = rows

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string in various formats."""
        formats = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        logger.warning(f"Could not parse date: {date_str}")
        return None

    def _find_exercise_columns(self, headers: List[str]) -> List[int]:
        """Find column indices for exercise data."""
        exercise_cols = []
        for i, header in enumerate(headers):
            if header.upper().startswith("E") and "(" in header:
                exercise_cols.append(i)
        return exercise_cols

    def _get_column_index(self, headers: List[str], name: str) -> Optional[int]:
        """Find column index by name (case-insensitive)."""
        name_lower = name.lower()
        for i, header in enumerate(headers):
            if header.lower() == name_lower:
                return i
        return None

    def _parse_optional_int(self, value: str) -> Optional[int]:
        """Parse string to int, returning None for empty/invalid values."""
        if not value or not value.strip():
            return None
        try:
            return int(value.strip())
        except ValueError:
            return None

    def _parse_optional_float(self, value: str) -> Optional[float]:
        """Parse string to float, returning None for empty/invalid values."""
        if not value or not value.strip():
            return None
        try:
            return float(value.strip())
        except ValueError:
            return None

    def _get_cell(self, row: List[str], idx: Optional[int]) -> str:
        """Safely get cell value from row."""
        if idx is not None and idx < len(row):
            return row[idx]
        return ""

    def parse(self) -> Iterator[LiftingWorkout]:
        """
        Parse workout data and yield LiftingWorkout objects.

        Yields:
            LiftingWorkout: Parsed workout data.
        """
        if not self._rows:
            return

        headers = self._rows[0]

        date_idx = self._get_column_index(headers, self.DATE_COLUMN)
        muscle_idx = self._get_column_index(headers, self.MUSCLE_GROUP_COLUMN)
        cardio_idx = self._get_column_index(headers, self.CARDIO_COLUMN)
        pushups_idx = self._get_column_index(headers, self.PUSHUPS_COLUMN)
        pullups_idx = self._get_column_index(headers, self.PULLUPS_COLUMN)
        weight_idx = self._get_column_index(headers, self.WEIGHT_COLUMN)
        memo_idx = self._get_column_index(headers, self.MEMO_COLUMN)
        exercise_indices = self._find_exercise_columns(headers)

        if date_idx is None:
            raise ValueError("Date column not found in workout data")

        for row_num, row in enumerate(self._rows[1:], start=2):
            date_val = self._get_cell(row, date_idx)
            if not date_val.strip():
                continue

            parsed_date = self._parse_date(date_val)
            if parsed_date is None:
                logger.warning(f"Skipping row {row_num}: invalid date")
                continue

            # parse exercises
            exercises = []
            for idx in exercise_indices:
                cell_val = self._get_cell(row, idx)
                if cell_val:
                    exercise = Exercise.from_string(cell_val)
                    if exercise:
                        exercises.append(exercise)

            # parse cardio
            cardio = None
            cardio_val = self._get_cell(row, cardio_idx)
            if cardio_val:
                cardio = CardioSession.from_string(cardio_val)

            workout = LiftingWorkout(
                date=parsed_date.date(),
                muscle_groups=self._get_cell(row, muscle_idx).strip() or "Unknown",
                exercises=exercises,
                cardio=cardio,
                pushups=self._parse_optional_int(self._get_cell(row, pushups_idx)),
                pullups=self._parse_optional_int(self._get_cell(row, pullups_idx)),
                bodyweight_lbs=self._parse_optional_float(
                    self._get_cell(row, weight_idx)
                ),
                notes=self._get_cell(row, memo_idx).strip() or None,
            )

            yield workout


class WorkoutSheetParser:
    """
    Parser for workout data from TSV/CSV files exported from Google Sheets.

    Handles the specific format of the workout tracking spreadsheet
    with exercise columns in format: type,weight,reps,rpe
    """

    # expected column names (case-insensitive matching)
    DATE_COLUMN = "date"
    MUSCLE_GROUP_COLUMN = "muscle group(s)"
    CARDIO_COLUMN = "cardio"
    PUSHUPS_COLUMN = "push-ups"
    PULLUPS_COLUMN = "pull-ups"
    WEIGHT_COLUMN = "weight"
    MEMO_COLUMN = "memo"

    def __init__(self, filepath: Path):
        """
        Initialize parser with file path.

        Parameters:
            filepath: Path to TSV or CSV file.
        """
        self._filepath = filepath
        self._delimiter = "\t" if filepath.suffix == ".tsv" else ","

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string in various formats.

        Parameters:
            date_str: Date string to parse.

        Returns:
            datetime if parsing succeeds, None otherwise.
        """
        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%d/%m/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None

    def _find_exercise_columns(self, headers: List[str]) -> List[int]:
        """
        Find column indices for exercise data (E1, E2, etc.).

        Parameters:
            headers: List of column headers.

        Returns:
            List of column indices containing exercise data.
        """
        exercise_cols = []
        for i, header in enumerate(headers):
            # match columns like "E1 (type,weight,reps,rpe)"
            if header.upper().startswith("E") and "(" in header:
                exercise_cols.append(i)
        return exercise_cols

    def _get_column_index(self, headers: List[str], name: str) -> Optional[int]:
        """
        Find column index by name (case-insensitive).

        Parameters:
            headers: List of column headers.
            name: Column name to find.

        Returns:
            Column index if found, None otherwise.
        """
        name_lower = name.lower()
        for i, header in enumerate(headers):
            if header.lower() == name_lower:
                return i
        return None

    def _parse_optional_int(self, value: str) -> Optional[int]:
        """Parse string to int, returning None for empty/invalid values."""
        if not value or not value.strip():
            return None
        try:
            return int(value.strip())
        except ValueError:
            return None

    def _parse_optional_float(self, value: str) -> Optional[float]:
        """Parse string to float, returning None for empty/invalid values."""
        if not value or not value.strip():
            return None
        try:
            return float(value.strip())
        except ValueError:
            return None

    def parse(self) -> Iterator[LiftingWorkout]:
        """
        Parse workout file and yield LiftingWorkout objects.

        Yields:
            LiftingWorkout: Parsed workout data.

        Raises:
            FileNotFoundError: If file does not exist.
        """
        if not self._filepath.exists():
            raise FileNotFoundError(f"Workout file not found: {self._filepath}")

        with open(self._filepath, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=self._delimiter)
            headers = next(reader)

            # find column indices
            date_idx = self._get_column_index(headers, self.DATE_COLUMN)
            muscle_idx = self._get_column_index(headers, self.MUSCLE_GROUP_COLUMN)
            cardio_idx = self._get_column_index(headers, self.CARDIO_COLUMN)
            pushups_idx = self._get_column_index(headers, self.PUSHUPS_COLUMN)
            pullups_idx = self._get_column_index(headers, self.PULLUPS_COLUMN)
            weight_idx = self._get_column_index(headers, self.WEIGHT_COLUMN)
            memo_idx = self._get_column_index(headers, self.MEMO_COLUMN)
            exercise_indices = self._find_exercise_columns(headers)

            if date_idx is None:
                raise ValueError("Date column not found in workout file")

            for row_num, row in enumerate(reader, start=2):
                if len(row) <= date_idx or not row[date_idx].strip():
                    continue

                parsed_date = self._parse_date(row[date_idx])
                if parsed_date is None:
                    logger.warning(f"Skipping row {row_num}: invalid date")
                    continue

                # parse exercises
                exercises = []
                for idx in exercise_indices:
                    if idx < len(row):
                        exercise = Exercise.from_string(row[idx])
                        if exercise:
                            exercises.append(exercise)

                # parse cardio
                cardio = None
                if cardio_idx and cardio_idx < len(row):
                    cardio = CardioSession.from_string(row[cardio_idx])

                # build workout
                workout = LiftingWorkout(
                    date=parsed_date.date(),
                    muscle_groups=(
                        row[muscle_idx].strip()
                        if muscle_idx and muscle_idx < len(row)
                        else "Unknown"
                    ),
                    exercises=exercises,
                    cardio=cardio,
                    pushups=(
                        self._parse_optional_int(row[pushups_idx])
                        if pushups_idx and pushups_idx < len(row)
                        else None
                    ),
                    pullups=(
                        self._parse_optional_int(row[pullups_idx])
                        if pullups_idx and pullups_idx < len(row)
                        else None
                    ),
                    bodyweight_lbs=(
                        self._parse_optional_float(row[weight_idx])
                        if weight_idx and weight_idx < len(row)
                        else None
                    ),
                    notes=(
                        row[memo_idx].strip()
                        if memo_idx and memo_idx < len(row)
                        else None
                    ),
                )

                yield workout


def load_workouts_from_file(filepath: Path) -> List[LiftingWorkout]:
    """
    Load all workouts from a TSV/CSV file.

    Parameters:
        filepath: Path to workout data file.

    Returns:
        List of parsed LiftingWorkout objects.
    """
    parser = WorkoutSheetParser(filepath)
    workouts = list(parser.parse())
    logger.info(f"Loaded {len(workouts)} workouts from {filepath}")
    return workouts


def load_workouts(
    filepath: Optional[Path] = None,
    use_api: bool = False,
    sheet_id: Optional[str] = None,
    range_name: str = "Sheet1",
) -> List[LiftingWorkout]:
    """
    Load workouts from either Google Sheets API or local file.

    Tries Google Sheets API first if use_api=True and credentials are available,
    otherwise falls back to local file.

    Parameters:
        filepath: Path to local TSV/CSV file (fallback).
        use_api: Whether to try Google Sheets API first.
        sheet_id: Google Sheet ID (or use GOOGLE_SHEET_ID env var).
        range_name: Sheet name or A1 range for API calls.

    Returns:
        List of parsed LiftingWorkout objects.
    """
    # try google sheets api if requested
    if use_api and GoogleSheetsClient.is_available():
        try:
            client = GoogleSheetsClient(sheet_id)
            workouts = client.fetch_workouts(range_name)
            if workouts:
                return workouts
            logger.warning("No workouts from API, falling back to file")
        except Exception as e:
            logger.warning(f"Google Sheets API error: {e}, falling back to file")

    # fall back to local file
    if filepath and filepath.exists():
        return load_workouts_from_file(filepath)

    logger.warning("No workout data source available")
    return []
