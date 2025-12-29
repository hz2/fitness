"""
Google Sheets client for fetching workout data.

Provides methods for reading workout data from Google Sheets,
either via API (requires credentials) or from exported TSV/CSV files.
"""

import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Iterator

from .models import LiftingWorkout, Exercise, CardioSession


logger = logging.getLogger(__name__)


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
