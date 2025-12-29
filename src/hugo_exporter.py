"""
Hugo static site exporter.

Exports workout data to JSON files compatible with Hugo's data
templates and shortcodes.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import asdict
from datetime import date, datetime

from .models import StravaActivity, LiftingWorkout, RunningStats, LiftingStats
from .analyzer import (
    calculate_running_stats,
    calculate_lifting_stats,
    calculate_weekly_mileage,
    calculate_monthly_mileage,
    calculate_weekly_volume,
    extract_locations,
)


logger = logging.getLogger(__name__)


class DateEncoder(json.JSONEncoder):
    """JSON encoder that handles date and datetime objects."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


class HugoExporter:
    """
    Exports workout data to Hugo-compatible JSON files.

    Creates data files in the Hugo site's data directory that can
    be accessed via site.Data in templates.
    """

    def __init__(self, hugo_data_dir: Path, hugo_content_dir: Path):
        """
        Initialize exporter with Hugo directories.

        Parameters:
            hugo_data_dir: Path to Hugo site's data directory.
            hugo_content_dir: Path to Hugo site's content directory.
        """
        self._data_dir = hugo_data_dir
        self._content_dir = hugo_content_dir

    def _ensure_dirs(self) -> None:
        """Create output directories if they don't exist."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._content_dir.mkdir(parents=True, exist_ok=True)

    def _write_json(self, filename: str, data: Any) -> None:
        """
        Write data to JSON file.

        Parameters:
            filename: Output filename (without path).
            data: Data to serialize.
        """
        filepath = self._data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, cls=DateEncoder)
        logger.info(f"Exported {filename}")

    def export_running_stats(self, activities: List[StravaActivity]) -> None:
        """
        Export running statistics to Hugo data file.

        Parameters:
            activities: List of Strava activities.
        """
        stats = calculate_running_stats(activities)

        data = {
            "total_runs": stats.total_runs,
            "total_miles": stats.total_miles,
            "total_time_hours": stats.total_time_hours,
            "total_elevation_feet": stats.total_elevation_feet,
            "avg_distance": stats.avg_distance,
            "avg_pace": stats.avg_pace,
            "fastest_pace": stats.fastest_pace,
            "longest_run_miles": stats.longest_run_miles,
            "runs_this_month": stats.runs_this_month,
            "miles_this_month": stats.miles_this_month,
            "fastest_run": stats.fastest_run,
            "longest_run": stats.longest_run,
        }

        self._write_json("running_stats.json", data)

    def export_recent_runs(
        self, activities: List[StravaActivity], limit: int = 10
    ) -> None:
        """
        Export recent runs to Hugo data file.

        Parameters:
            activities: List of Strava activities.
            limit: Maximum number of runs to export.
        """
        from .models import ActivityType

        runs = [a for a in activities if a.activity_type == ActivityType.RUN][:limit]

        data = [
            {
                "name": run.name,
                "date": run.date.isoformat(),
                "distance_miles": run.distance_miles,
                "moving_time_minutes": round(run.moving_time_minutes, 1),
                "pace_per_mile": run.pace_per_mile,
                "elevation_gain_feet": run.elevation_gain_feet,
            }
            for run in runs
        ]

        self._write_json("recent_runs.json", data)

    def export_running_locations(
        self, activities: List[StravaActivity], limit: int = 10
    ) -> None:
        """
        Export top running locations to Hugo data file.

        Parameters:
            activities: List of Strava activities.
            limit: Maximum number of locations to export.
        """
        locations = extract_locations(activities)[:limit]
        self._write_json("running_locations.json", locations)

    def export_weekly_mileage(self, activities: List[StravaActivity]) -> None:
        """
        Export weekly mileage data for charts.

        Parameters:
            activities: List of Strava activities.
        """
        data = calculate_weekly_mileage(activities)
        self._write_json("weekly_mileage.json", data)

    def export_monthly_mileage(self, activities: List[StravaActivity]) -> None:
        """
        Export monthly mileage data for charts.

        Parameters:
            activities: List of Strava activities.
        """
        data = calculate_monthly_mileage(activities)
        self._write_json("monthly_mileage.json", data)

    def export_lifting_stats(self, workouts: List[LiftingWorkout]) -> None:
        """
        Export lifting statistics to Hugo data file.

        Parameters:
            workouts: List of lifting workouts.
        """
        stats = calculate_lifting_stats(workouts)

        data = {
            "total_workouts": stats.total_workouts,
            "total_volume_lbs": stats.total_volume_lbs,
            "workout_distribution": [
                {"group": group, "count": count}
                for group, count in stats.workout_distribution.items()
            ],
            "date_range": {
                "start": stats.date_range_start.isoformat(),
                "end": stats.date_range_end.isoformat(),
            },
        }

        self._write_json("workout_summary.json", data)

    def export_lifting_prs(
        self, workouts: List[LiftingWorkout], limit: int = 20
    ) -> None:
        """
        Export personal records to Hugo data file.

        Parameters:
            workouts: List of lifting workouts.
            limit: Maximum number of PRs to export.
        """
        stats = calculate_lifting_stats(workouts)
        prs = stats.personal_records[:limit]
        self._write_json("lifting_prs.json", prs)

    def export_weekly_volume(self, workouts: List[LiftingWorkout]) -> None:
        """
        Export weekly lifting volume for charts.

        Parameters:
            workouts: List of lifting workouts.
        """
        data = calculate_weekly_volume(workouts)
        self._write_json("weekly_volume.json", data)

    def export_all(
        self, activities: List[StravaActivity], workouts: List[LiftingWorkout]
    ) -> None:
        """
        Export all data to Hugo site.

        Parameters:
            activities: List of Strava activities.
            workouts: List of lifting workouts.
        """
        self._ensure_dirs()

        # running data
        if activities:
            logger.info("Exporting Strava data...")
            self.export_running_stats(activities)
            self.export_recent_runs(activities)
            self.export_running_locations(activities)
            self.export_weekly_mileage(activities)
            self.export_monthly_mileage(activities)

        # lifting data
        if workouts:
            logger.info("Exporting lifting data...")
            self.export_lifting_stats(workouts)
            self.export_lifting_prs(workouts)
            self.export_weekly_volume(workouts)

        logger.info(f"Export complete. Data written to {self._data_dir}")
