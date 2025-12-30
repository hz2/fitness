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
    calculate_rep_range_records,
    calculate_strength_standards,
    calculate_training_frequency,
    calculate_volume_by_muscle_group,
    calculate_exercise_volume_trend,
    calculate_advanced_lifting_stats,
    calculate_running_streaks,
    calculate_pace_zones,
    calculate_heart_rate_stats,
    calculate_running_prs,
    calculate_monthly_trends,
    calculate_advanced_running_stats,
    calculate_key_lift_prs,
    filter_cardio_workouts,
    calculate_accessory_prs,
)


logger = logging.getLogger(__name__)


class DateEncoder(json.JSONEncoder):
    """JSON encoder that handles date and datetime objects."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


class HugoExporter:
    """Exports workout data to Hugo-compatible JSON files."""

    def __init__(self, hugo_data_dir: Path, hugo_content_dir: Path):
        """Initialize exporter with Hugo directories."""
        self._data_dir = hugo_data_dir
        self._content_dir = hugo_content_dir

    def _ensure_dirs(self) -> None:
        """Create output directories if they don't exist."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._content_dir.mkdir(parents=True, exist_ok=True)

    def _write_json(self, filename: str, data: Any) -> None:
        """Write data to JSON file."""
        filepath = self._data_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, cls=DateEncoder)
        logger.info(f"Exported {filename}")

    def export_running_stats(self, activities: List[StravaActivity]) -> None:
        """Export running statistics to Hugo data file."""
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
        self, activities: List[StravaActivity], limit: int = 5
    ) -> None:
        """Export recent runs to Hugo data file."""
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
                "average_heartrate": run.average_heartrate,
                "suffer_score": run.suffer_score,
                "calories": run.calories,
            }
            for run in runs
        ]

        self._write_json("recent_runs.json", data)

    def export_running_locations(
        self, activities: List[StravaActivity], limit: int = 10
    ) -> None:
        """Export top running locations to Hugo data file."""
        locations = extract_locations(activities)[:limit]
        self._write_json("running_locations.json", locations)

    def export_weekly_mileage(self, activities: List[StravaActivity]) -> None:
        """Export weekly mileage data for charts."""
        data = calculate_weekly_mileage(activities)
        self._write_json("weekly_mileage.json", data)

    def export_monthly_mileage(self, activities: List[StravaActivity]) -> None:
        """Export monthly mileage data for charts."""
        data = calculate_monthly_mileage(activities)
        self._write_json("monthly_mileage.json", data)

    def export_lifting_stats(self, workouts: List[LiftingWorkout]) -> None:
        """Export lifting statistics to Hugo data file."""
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
        """Export personal records to Hugo data file."""
        stats = calculate_lifting_stats(workouts)
        prs = stats.personal_records[:limit]
        self._write_json("lifting_prs.json", prs)

    def export_weekly_volume(self, workouts: List[LiftingWorkout]) -> None:
        """Export weekly lifting volume for charts."""
        data = calculate_weekly_volume(workouts)
        self._write_json("weekly_volume.json", data)

    def export_rep_range_prs(
        self, workouts: List[LiftingWorkout], min_reps: int = 8, max_reps: int = 10
    ) -> None:
        """Export personal records within a rep range."""
        data = calculate_rep_range_records(workouts, min_reps, max_reps)
        self._write_json("rep_range_prs.json", data)

    def export_strength_standards(self, workouts: List[LiftingWorkout]) -> None:
        """Export strength standards relative to bodyweight."""
        # get latest bodyweight
        bodyweights = [w.bodyweight_lbs for w in workouts if w.bodyweight_lbs]
        bw = bodyweights[-1] if bodyweights else 180.0

        data = calculate_strength_standards(workouts, bw)
        self._write_json("strength_standards.json", data)

    def export_training_frequency(self, workouts: List[LiftingWorkout]) -> None:
        """Export training frequency statistics."""
        data = calculate_training_frequency(workouts)
        self._write_json("training_frequency.json", data)

    def export_volume_by_muscle(self, workouts: List[LiftingWorkout]) -> None:
        """Export volume breakdown by muscle group."""
        volume_dict = calculate_volume_by_muscle_group(workouts)
        data = [
            {"muscle_group": group, "volume": round(vol, 0)}
            for group, vol in volume_dict.items()
        ]
        self._write_json("volume_by_muscle.json", data)

    def export_volume_trend(self, workouts: List[LiftingWorkout]) -> None:
        """Export volume trend with rolling average."""
        data = calculate_exercise_volume_trend(workouts)
        self._write_json("volume_trend.json", data)

    def export_advanced_stats(self, workouts: List[LiftingWorkout]) -> None:
        """Export all advanced lifting statistics to a single file."""
        data = calculate_advanced_lifting_stats(workouts)
        self._write_json("advanced_lifting_stats.json", data)

    def export_key_lift_prs(self, workouts: List[LiftingWorkout]) -> None:
        """Export key compound lift PRs across multiple rep ranges."""
        # Filter cardio first
        lifting_workouts = filter_cardio_workouts(workouts)
        data = calculate_key_lift_prs(lifting_workouts)
        self._write_json("key_lift_prs.json", data)

    def export_accessory_prs(self, workouts: List[LiftingWorkout]) -> None:
        """Export accessory lift PRs."""
        lifting_workouts = filter_cardio_workouts(workouts)
        data = calculate_accessory_prs(lifting_workouts)
        self._write_json("accessory_prs.json", data)
        logger.info("Exported accessory_prs.json")

    def export_running_prs(self, activities: List[StravaActivity]) -> None:
        """Export running personal records."""
        data = calculate_running_prs(activities)
        self._write_json("running_prs.json", data)

    def export_pace_zones(self, activities: List[StravaActivity]) -> None:
        """Export pace zone distribution."""
        data = calculate_pace_zones(activities)
        self._write_json("pace_zones.json", data)

    def export_running_streaks(self, activities: List[StravaActivity]) -> None:
        """Export running streak data."""
        data = calculate_running_streaks(activities)
        self._write_json("running_streaks.json", data)

    def export_heart_rate_stats(self, activities: List[StravaActivity]) -> None:
        """Export heart rate statistics."""
        data = calculate_heart_rate_stats(activities)
        self._write_json("heart_rate_stats.json", data)

    def export_advanced_running_stats(self, activities: List[StravaActivity]) -> None:
        """Export all advanced running statistics to a single file."""
        data = calculate_advanced_running_stats(activities)
        self._write_json("advanced_running_stats.json", data)

    def export_all(
        self, activities: List[StravaActivity], workouts: List[LiftingWorkout]
    ) -> None:
        """Export all data to Hugo site."""
        self._ensure_dirs()

        # running data from Strava
        if activities:
            logger.info("Exporting Strava data...")
            self.export_running_stats(activities)
            self.export_recent_runs(activities, limit=5)
            self.export_running_locations(activities)
            self.export_weekly_mileage(activities)
            self.export_monthly_mileage(activities)
            # new advanced running stats
            self.export_running_prs(activities)
            self.export_pace_zones(activities)
            self.export_running_streaks(activities)
            self.export_heart_rate_stats(activities)
            self.export_advanced_running_stats(activities)

        # lifting data (filter cardio since Strava tracks cardio)
        if workouts:
            logger.info("Exporting lifting data...")
            lifting_only = filter_cardio_workouts(workouts)
            self.export_lifting_stats(workouts)  # already filters internally
            self.export_lifting_prs(lifting_only)
            self.export_weekly_volume(lifting_only)
            # advanced lifting stats
            self.export_rep_range_prs(lifting_only)
            self.export_strength_standards(lifting_only)
            self.export_training_frequency(lifting_only)
            self.export_volume_by_muscle(lifting_only)
            self.export_volume_trend(lifting_only)
            self.export_key_lift_prs(workouts)  # already filters internally
            self.export_accessory_prs(workouts)  # already filters internally
            self.export_advanced_stats(workouts)  # already filters internally

        logger.info(f"Export complete. Data written to {self._data_dir}")
