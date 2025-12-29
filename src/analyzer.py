"""
Workout data analyzer.

Provides functions for calculating statistics and aggregating
workout data from both Strava and lifting workouts.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from .models import (
    StravaActivity,
    LiftingWorkout,
    RunningStats,
    LiftingStats,
    ActivityType,
)


logger = logging.getLogger(__name__)


def calculate_running_stats(activities: List[StravaActivity]) -> RunningStats:
    """
    Calculate aggregate running statistics.

    Parameters:
        activities: List of Strava activities.

    Returns:
        RunningStats: Aggregated running statistics.
    """
    runs = [a for a in activities if a.activity_type == ActivityType.RUN]

    if not runs:
        return RunningStats(
            total_runs=0,
            total_miles=0.0,
            total_time_hours=0.0,
            total_elevation_feet=0.0,
            avg_distance=0.0,
            avg_pace="N/A",
            fastest_pace="N/A",
            longest_run_miles=0.0,
            runs_this_month=0,
            miles_this_month=0.0,
        )

    total_miles = sum(r.distance_miles for r in runs)
    total_seconds = sum(r.moving_time_seconds for r in runs)
    total_elevation = sum(r.elevation_gain_feet for r in runs)

    # calculate paces (filter out zero-distance activities)
    valid_paces = [r.pace_seconds for r in runs if r.pace_seconds]
    avg_pace_secs = sum(valid_paces) / len(valid_paces) if valid_paces else 0
    fastest_pace_secs = min(valid_paces) if valid_paces else 0

    # this month's stats
    month_start = (
        datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
    )
    month_runs = [r for r in runs if r.date >= month_start]

    # find fastest and longest runs
    fastest_run = None
    longest_run = None

    if valid_paces:
        fastest = min(runs, key=lambda r: r.pace_seconds or float("inf"))
        fastest_run = {
            "name": fastest.name,
            "date": fastest.date.isoformat(),
            "distance": fastest.distance_miles,
            "pace": fastest.pace_per_mile,
        }

    if runs:
        longest = max(runs, key=lambda r: r.distance_miles)
        longest_run = {
            "name": longest.name,
            "date": longest.date.isoformat(),
            "distance": longest.distance_miles,
            "pace": longest.pace_per_mile,
        }

    return RunningStats(
        total_runs=len(runs),
        total_miles=round(total_miles, 1),
        total_time_hours=round(total_seconds / 3600, 1),
        total_elevation_feet=round(total_elevation, 0),
        avg_distance=round(total_miles / len(runs), 2),
        avg_pace=_format_pace(avg_pace_secs),
        fastest_pace=_format_pace(fastest_pace_secs),
        longest_run_miles=max(r.distance_miles for r in runs),
        runs_this_month=len(month_runs),
        miles_this_month=round(sum(r.distance_miles for r in month_runs), 1),
        fastest_run=fastest_run,
        longest_run=longest_run,
    )


def calculate_lifting_stats(workouts: List[LiftingWorkout]) -> LiftingStats:
    """
    Calculate aggregate lifting statistics.

    Parameters:
        workouts: List of lifting workouts.

    Returns:
        LiftingStats: Aggregated lifting statistics.
    """
    if not workouts:
        return LiftingStats(
            total_workouts=0,
            total_volume_lbs=0.0,
            workout_distribution={},
            date_range_start=datetime.now().date(),
            date_range_end=datetime.now().date(),
        )

    total_volume = sum(w.total_volume for w in workouts)

    # workout distribution by muscle group
    distribution: Dict[str, int] = defaultdict(int)
    for workout in workouts:
        distribution[workout.muscle_groups] += 1

    # date range
    dates = [w.date for w in workouts]
    date_start = min(dates)
    date_end = max(dates)

    # personal records (max weight per exercise)
    prs = calculate_personal_records(workouts)

    return LiftingStats(
        total_workouts=len(workouts),
        total_volume_lbs=round(total_volume, 0),
        workout_distribution=dict(distribution),
        date_range_start=date_start,
        date_range_end=date_end,
        personal_records=prs,
    )


def calculate_personal_records(workouts: List[LiftingWorkout]) -> List[Dict]:
    """
    Calculate personal records for each exercise.

    Parameters:
        workouts: List of lifting workouts.

    Returns:
        List of PR dictionaries sorted by weight descending.
    """
    exercise_maxes: Dict[str, Tuple[float, int, str]] = {}

    for workout in workouts:
        for exercise in workout.exercises:
            name = exercise.name.lower().strip()
            current = exercise_maxes.get(name)

            if current is None or exercise.weight_lbs > current[0]:
                exercise_maxes[name] = (
                    exercise.weight_lbs,
                    exercise.reps,
                    workout.date.isoformat(),
                )

    prs = [
        {
            "exercise": name,
            "max_weight": weight,
            "reps": reps,
            "date": date,
        }
        for name, (weight, reps, date) in exercise_maxes.items()
    ]

    return sorted(prs, key=lambda x: x["max_weight"], reverse=True)


def calculate_weekly_mileage(activities: List[StravaActivity]) -> List[Dict]:
    """
    Calculate weekly running mileage.

    Parameters:
        activities: List of Strava activities.

    Returns:
        List of weekly mileage dictionaries.
    """
    runs = [a for a in activities if a.activity_type == ActivityType.RUN]

    if not runs:
        return []

    # group by year-week
    weekly: Dict[Tuple[int, int], Dict] = defaultdict(
        lambda: {"miles": 0.0, "runs": 0, "minutes": 0.0}
    )

    for run in runs:
        iso = run.date.isocalendar()
        key = (iso.year, iso.week)
        weekly[key]["miles"] += run.distance_miles
        weekly[key]["runs"] += 1
        weekly[key]["minutes"] += run.moving_time_minutes
        if "date" not in weekly[key]:
            weekly[key]["date"] = run.date

    result = []
    for (year, week), data in sorted(weekly.items()):
        result.append(
            {
                "week": f"{year}-W{week:02d}",
                "miles": round(data["miles"], 1),
                "runs": data["runs"],
                "minutes": round(data["minutes"], 1),
                "date": (
                    data.get("date", "").isoformat()
                    if hasattr(data.get("date"), "isoformat")
                    else ""
                ),
            }
        )

    return result


def calculate_monthly_mileage(activities: List[StravaActivity]) -> List[Dict]:
    """
    Calculate monthly running mileage.

    Parameters:
        activities: List of Strava activities.

    Returns:
        List of monthly mileage dictionaries.
    """
    runs = [a for a in activities if a.activity_type == ActivityType.RUN]

    if not runs:
        return []

    monthly: Dict[str, Dict] = defaultdict(
        lambda: {"miles": 0.0, "runs": 0, "minutes": 0.0}
    )

    for run in runs:
        key = run.date.strftime("%Y-%m")
        monthly[key]["miles"] += run.distance_miles
        monthly[key]["runs"] += 1
        monthly[key]["minutes"] += run.moving_time_minutes

    return [
        {
            "month": month,
            "miles": round(data["miles"], 1),
            "runs": data["runs"],
            "hours": round(data["minutes"] / 60, 1),
        }
        for month, data in sorted(monthly.items())
    ]


def extract_locations(activities: List[StravaActivity]) -> List[Dict]:
    """
    Extract running locations from activity names.

    Parses activity names in format "[time] location" to extract
    location information.

    Parameters:
        activities: List of Strava activities.

    Returns:
        List of location dictionaries sorted by run count.
    """
    runs = [a for a in activities if a.activity_type == ActivityType.RUN]

    locations: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "miles": 0.0})

    for run in runs:
        name = run.name.lower()
        # extract location from "[time] location" format
        if "]" in name:
            loc = name.split("]")[-1].strip()
        else:
            loc = name.strip()

        if loc:
            locations[loc]["count"] += 1
            locations[loc]["miles"] += run.distance_miles

    return sorted(
        [
            {"name": name, "count": data["count"], "miles": round(data["miles"], 1)}
            for name, data in locations.items()
        ],
        key=lambda x: x["count"],
        reverse=True,
    )


def calculate_weekly_volume(workouts: List[LiftingWorkout]) -> List[Dict]:
    """
    Calculate weekly lifting volume.

    Parameters:
        workouts: List of lifting workouts.

    Returns:
        List of weekly volume dictionaries.
    """
    if not workouts:
        return []

    weekly: Dict[Tuple[int, int], Dict] = defaultdict(
        lambda: {"volume": 0.0, "workouts": 0}
    )

    for workout in workouts:
        iso = workout.date.isocalendar()
        key = (iso.year, iso.week)
        weekly[key]["volume"] += workout.total_volume
        weekly[key]["workouts"] += 1
        if "date" not in weekly[key]:
            weekly[key]["date"] = workout.date

    result = []
    for (year, week), data in sorted(weekly.items()):
        result.append(
            {
                "week": f"{year}-W{week:02d}",
                "volume": round(data["volume"], 0),
                "workouts": data["workouts"],
                "date": (
                    data.get("date", "").isoformat()
                    if hasattr(data.get("date"), "isoformat")
                    else ""
                ),
            }
        )

    return result


def _format_pace(seconds: float) -> str:
    """
    Format pace in seconds to mm:ss string.

    Parameters:
        seconds: Pace in seconds per mile.

    Returns:
        Formatted pace string.
    """
    if seconds <= 0:
        return "N/A"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"
