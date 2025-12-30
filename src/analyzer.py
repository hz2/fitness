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


# =============================================================================
# EXERCISE NAME NORMALIZATION
# =============================================================================

# Maps various exercise name variations to canonical names
EXERCISE_ALIASES: Dict[str, str] = {
    # Bench Press variations
    "flat bb bench press": "bench press",
    "flat bb bench": "bench press",
    "bb bench press": "bench press",
    "bb bench": "bench press",
    "barbell bench": "bench press",
    "barbell bench press": "bench press",
    "flat bench": "bench press",
    "flat bench press": "bench press",
    "paused bb bench": "bench press",
    "paused bench": "bench press",
    # DB Bench variations
    "flat db press": "db bench press",
    "flat db bench": "db bench press",
    "flat db bench press": "db bench press",
    "db flat bench": "db bench press",
    "db press": "db bench press",
    "db bench": "db bench press",
    "dumbbell bench": "db bench press",
    # Incline bench
    "db incline press": "incline db press",
    "incline db bench": "incline db press",
    "incline db bench press": "incline db press",
    "incline chest press machine": "incline press",
    # Squat variations
    "bb squat": "squat",
    "barbell squat": "squat",
    "back squat": "squat",
    "bb back squat": "squat",
    "sumo bb squat": "sumo squat",
    "sumo squat": "sumo squat",
    # Deadlift variations
    "conventional deadlift": "deadlift",
    "bb deadlift": "deadlift",
    "barbell deadlift": "deadlift",
    "sumo deadlift": "sumo deadlift",
    "rdl": "romanian deadlift",
    "db rdl": "db romanian deadlift",
    # Overhead press
    "military press": "overhead press",
    "ohp": "overhead press",
    "bb overhead press": "overhead press",
    "bb military press": "overhead press",
    "standing press": "overhead press",
    "db shoulder press": "db overhead press",
    "seated shoulder press": "db overhead press",
    "db ohp": "db overhead press",
    # Row variations
    "bb row": "barbell row",
    "bb-row": "barbell row",
    "bb-underhand row": "barbell row",
    "underhand bb row": "barbell row",
    "bent over row": "barbell row",
    "pendlay row": "barbell row",
    "t-bar row": "t-bar row",
    "chest supported db rows": "db row",
    "chest supported db row": "db row",
    "cable row": "cable row",
    "seated cable row": "cable row",
}

# Key compound lifts to track for rep range PRs (the big 3 + variations)
KEY_COMPOUND_LIFTS = {
    "bench press",
    "db bench press",
    "squat",
    "hack squat",
    "deadlift",
    "sumo deadlift",
    "romanian deadlift",
}

# The big 3 lifts for 1RM tracking
BIG_THREE_LIFTS = {
    "bench press",
    "squat",
    "deadlift",
}

# Accessory lifts to track separately
ACCESSORY_LIFTS = {
    "db press": ["db press", "dumbbell press", "flat db press", "incline db press"],
    "lat pulldown": ["lat pulldown", "lat pull down", "lat pull-down", "cable lat pulldown"],
    "pull-ups": ["pull-ups", "pullups", "pull ups", "chin-ups", "chinups", "chin ups"],
    "push-ups": ["push-ups", "pushups", "push ups"],
    "helms row": ["helms row", "helm row", "chest supported row"],
}


def normalize_exercise_name(name: str) -> str:
    """Normalize exercise name to canonical form."""
    name_lower = name.lower().strip()
    return EXERCISE_ALIASES.get(name_lower, name_lower)


def is_key_compound_lift(name: str) -> bool:
    """Check if exercise is a key compound lift worth tracking."""
    normalized = normalize_exercise_name(name)
    return normalized in KEY_COMPOUND_LIFTS


def filter_cardio_workouts(workouts: List[LiftingWorkout]) -> List[LiftingWorkout]:
    """Filter out cardio-only workouts from the list."""
    return [w for w in workouts if w.muscle_groups.lower() != "cardio"]


def calculate_running_stats(activities: List[StravaActivity]) -> RunningStats:
    """Calculate aggregate running statistics."""
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
    """Calculate aggregate lifting statistics. Filters out cardio workouts."""
    # Filter out cardio workouts
    lifting_workouts = filter_cardio_workouts(workouts)

    if not lifting_workouts:
        return LiftingStats(
            total_workouts=0,
            total_volume_lbs=0.0,
            workout_distribution={},
            date_range_start=datetime.now().date(),
            date_range_end=datetime.now().date(),
        )

    total_volume = sum(w.total_volume for w in lifting_workouts)

    # workout distribution by muscle group
    distribution: Dict[str, int] = defaultdict(int)
    for workout in lifting_workouts:
        distribution[workout.muscle_groups] += 1

    # date range
    dates = [w.date for w in lifting_workouts]
    date_start = min(dates)
    date_end = max(dates)

    # personal records (max weight per exercise)
    prs = calculate_personal_records(lifting_workouts)

    return LiftingStats(
        total_workouts=len(lifting_workouts),
        total_volume_lbs=round(total_volume, 0),
        workout_distribution=dict(distribution),
        date_range_start=date_start,
        date_range_end=date_end,
        personal_records=prs,
    )


def calculate_personal_records(workouts: List[LiftingWorkout]) -> List[Dict]:
    """Calculate personal records for each exercise."""
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
    """Calculate weekly running mileage."""
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
    """Calculate monthly running mileage."""
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
    """Extract running locations from activity names."""
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
    """Calculate weekly lifting volume."""
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
    """Format pace in seconds to mm:ss string."""
    if seconds <= 0:
        return "N/A"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def calculate_estimated_1rm(weight: float, reps: int) -> float:
    """Calculate estimated 1RM using Brzycki formula: weight * (36 / (37 - reps))."""
    if reps <= 0 or reps >= 37:
        return weight
    return weight * (36 / (37 - reps))


def calculate_rep_range_records(
    workouts: List[LiftingWorkout],
    min_reps: int = 8,
    max_reps: int = 10,
    key_lifts_only: bool = True,
) -> List[Dict]:
    """Calculate PRs within a rep range, with normalized exercise names."""
    exercise_records: Dict[str, Dict] = {}

    for workout in workouts:
        for exercise in workout.exercises:
            if min_reps <= exercise.reps <= max_reps:
                normalized_name = normalize_exercise_name(exercise.name)

                # skip non-key lifts if filtering
                if key_lifts_only and not is_key_compound_lift(exercise.name):
                    continue

                current = exercise_records.get(normalized_name)
                estimated_1rm = calculate_estimated_1rm(
                    exercise.weight_lbs, exercise.reps
                )

                if current is None or estimated_1rm > current["estimated_1rm"]:
                    exercise_records[normalized_name] = {
                        "exercise": normalized_name,
                        "weight": exercise.weight_lbs,
                        "reps": exercise.reps,
                        "rpe": exercise.rpe,
                        "date": workout.date.isoformat(),
                        "estimated_1rm": round(estimated_1rm, 1),
                    }

    return sorted(
        list(exercise_records.values()),
        key=lambda x: x["estimated_1rm"],
        reverse=True,
    )


def calculate_key_lift_prs(workouts: List[LiftingWorkout]) -> List[Dict]:
    """Calculate PRs for squat, bench, deadlift across rep ranges."""
    # Rep range definitions
    rep_ranges = {
        "strength": (1, 5),
        "hypertrophy": (6, 10),
        "endurance": (11, 20),
    }

    # Track best for each exercise and rep range
    lift_records: Dict[str, Dict[str, Dict]] = defaultdict(dict)

    # Also track recent performance (last 2 weeks)
    two_weeks_ago = datetime.now().date() - timedelta(days=14)
    recent_lifts: Dict[str, Dict] = {}

    for workout in workouts:
        for exercise in workout.exercises:
            normalized_name = normalize_exercise_name(exercise.name)

            # Only track the big 3 lifts
            if normalized_name not in BIG_THREE_LIFTS:
                continue

            estimated_1rm = calculate_estimated_1rm(exercise.weight_lbs, exercise.reps)

            # Determine which rep range this falls into
            for range_name, (min_r, max_r) in rep_ranges.items():
                if min_r <= exercise.reps <= max_r:
                    current = lift_records[normalized_name].get(range_name)

                    if current is None or estimated_1rm > current["estimated_1rm"]:
                        lift_records[normalized_name][range_name] = {
                            "weight": exercise.weight_lbs,
                            "reps": exercise.reps,
                            "rpe": exercise.rpe,
                            "date": workout.date.isoformat(),
                            "estimated_1rm": round(estimated_1rm, 1),
                        }
                    break

            # Track most recent lift for context
            if workout.date >= two_weeks_ago:
                current_recent = recent_lifts.get(normalized_name)
                if (
                    current_recent is None
                    or workout.date.isoformat() > current_recent["date"]
                ):
                    recent_lifts[normalized_name] = {
                        "weight": exercise.weight_lbs,
                        "reps": exercise.reps,
                        "rpe": exercise.rpe,
                        "date": workout.date.isoformat(),
                    }

    # Build output with all rep ranges and recent context
    results = []
    for exercise_name, ranges in lift_records.items():
        record = {
            "exercise": exercise_name,
            "strength_pr": ranges.get("strength"),
            "hypertrophy_pr": ranges.get("hypertrophy"),
            "endurance_pr": ranges.get("endurance"),
            "recent": recent_lifts.get(exercise_name),
        }

        # Calculate best estimated 1RM across all ranges
        best_e1rm = 0
        for range_data in ranges.values():
            if range_data and range_data["estimated_1rm"] > best_e1rm:
                best_e1rm = range_data["estimated_1rm"]

        record["best_estimated_1rm"] = best_e1rm
        results.append(record)

    return sorted(results, key=lambda x: x["best_estimated_1rm"], reverse=True)


def calculate_exercise_progression(
    workouts: List[LiftingWorkout], exercise_name: str
) -> List[Dict]:
    """Track progression of a specific exercise over time."""
    name_lower = exercise_name.lower().strip()
    progression = []

    for workout in sorted(workouts, key=lambda w: w.date):
        for exercise in workout.exercises:
            if exercise.name.lower().strip() == name_lower:
                progression.append(
                    {
                        "date": workout.date.isoformat(),
                        "weight": exercise.weight_lbs,
                        "reps": exercise.reps,
                        "rpe": exercise.rpe,
                        "volume": exercise.volume,
                        "estimated_1rm": round(
                            calculate_estimated_1rm(exercise.weight_lbs, exercise.reps),
                            1,
                        ),
                    }
                )

    return progression


def calculate_volume_by_muscle_group(
    workouts: List[LiftingWorkout],
) -> Dict[str, float]:
    """Calculate total volume per muscle group."""
    volume_by_group: Dict[str, float] = defaultdict(float)

    for workout in workouts:
        volume_by_group[workout.muscle_groups] += workout.total_volume

    return dict(sorted(volume_by_group.items(), key=lambda x: x[1], reverse=True))


def calculate_training_frequency(workouts: List[LiftingWorkout]) -> Dict:
    """Calculate training frequency statistics."""
    if not workouts:
        return {"avg_days_between": 0, "workouts_per_week": 0}

    sorted_workouts = sorted(workouts, key=lambda w: w.date)

    # calculate days between workouts
    gaps = []
    for i in range(1, len(sorted_workouts)):
        gap = (sorted_workouts[i].date - sorted_workouts[i - 1].date).days
        gaps.append(gap)

    avg_gap = sum(gaps) / len(gaps) if gaps else 0

    # workouts per week over the entire period
    if len(sorted_workouts) >= 2:
        total_days = (sorted_workouts[-1].date - sorted_workouts[0].date).days
        weeks = max(total_days / 7, 1)
        workouts_per_week = len(workouts) / weeks
    else:
        workouts_per_week = len(workouts)

    # muscle group frequency
    group_counts: Dict[str, int] = defaultdict(int)
    for workout in workouts:
        group_counts[workout.muscle_groups] += 1

    return {
        "avg_days_between": round(avg_gap, 1),
        "workouts_per_week": round(workouts_per_week, 1),
        "total_workouts": len(workouts),
        "muscle_group_frequency": dict(group_counts),
    }


def calculate_strength_standards(
    workouts: List[LiftingWorkout], bodyweight: float = 180.0
) -> List[Dict]:
    """Calculate strength relative to bodyweight for the big 3 lifts."""
    # find max for each key lift pattern
    lift_maxes: Dict[str, Dict] = {}

    for workout in workouts:
        for exercise in workout.exercises:
            name_lower = exercise.name.lower().strip()

            # categorize the lift - only big 3
            category = None
            if any(
                k in name_lower for k in ["bench", "chest press", "db press", "flat db"]
            ):
                category = "Bench Press"
            elif any(k in name_lower for k in ["squat"]):
                category = "Squat"
            elif any(k in name_lower for k in ["deadlift", "rdl"]):
                category = "Deadlift"

            if category:
                e1rm = calculate_estimated_1rm(exercise.weight_lbs, exercise.reps)
                current = lift_maxes.get(category)

                if current is None or e1rm > current["estimated_1rm"]:
                    lift_maxes[category] = {
                        "lift": category,
                        "exercise": exercise.name,
                        "weight": exercise.weight_lbs,
                        "reps": exercise.reps,
                        "estimated_1rm": round(e1rm, 1),
                        "bw_ratio": round(e1rm / bodyweight, 2),
                        "date": workout.date.isoformat(),
                    }

    return sorted(list(lift_maxes.values()), key=lambda x: x["bw_ratio"], reverse=True)


def calculate_accessory_prs(workouts: List[LiftingWorkout]) -> List[Dict]:
    """Calculate PRs for accessory lifts."""
    lift_maxes: Dict[str, Dict] = {}

    for workout in workouts:
        # Check push-ups from dedicated column
        if workout.pushups and workout.pushups > 0:
            current = lift_maxes.get("push-ups")
            if current is None or workout.pushups > current["reps"]:
                lift_maxes["push-ups"] = {
                    "lift": "push-ups",
                    "exercise": "push-ups",
                    "weight": 0.0,
                    "reps": workout.pushups,
                    "date": workout.date.isoformat(),
                }

        # Check pull-ups from dedicated column
        if workout.pullups and workout.pullups > 0:
            current = lift_maxes.get("pull-ups")
            if current is None or workout.pullups > current["reps"]:
                lift_maxes["pull-ups"] = {
                    "lift": "pull-ups",
                    "exercise": "pull-ups",
                    "weight": 0.0,
                    "reps": workout.pullups,
                    "date": workout.date.isoformat(),
                }

        for exercise in workout.exercises:
            name_lower = exercise.name.lower().strip()

            # check against accessory lift patterns
            category = None
            for lift_name, patterns in ACCESSORY_LIFTS.items():
                if any(p in name_lower for p in patterns):
                    category = lift_name
                    break

            if category:
                # for bodyweight exercises, track max reps
                if category in ["pull-ups", "push-ups"]:
                    current = lift_maxes.get(category)
                    if current is None or exercise.reps > current["reps"]:
                        lift_maxes[category] = {
                            "lift": category,
                            "exercise": exercise.name,
                            "weight": exercise.weight_lbs,
                            "reps": exercise.reps,
                            "date": workout.date.isoformat(),
                        }
                else:
                    # for weighted exercises, track by estimated 1RM
                    e1rm = calculate_estimated_1rm(exercise.weight_lbs, exercise.reps)
                    current = lift_maxes.get(category)

                    if current is None or e1rm > current.get("estimated_1rm", 0):
                        lift_maxes[category] = {
                            "lift": category,
                            "exercise": exercise.name,
                            "weight": exercise.weight_lbs,
                            "reps": exercise.reps,
                            "estimated_1rm": round(e1rm, 1),
                            "date": workout.date.isoformat(),
                        }

    return list(lift_maxes.values())


def calculate_exercise_volume_trend(
    workouts: List[LiftingWorkout], window_weeks: int = 4
) -> List[Dict]:
    """Calculate rolling average volume trend."""
    weekly = calculate_weekly_volume(workouts)

    if len(weekly) < window_weeks:
        return weekly

    # add rolling average
    for i, week in enumerate(weekly):
        if i >= window_weeks - 1:
            window = weekly[i - window_weeks + 1 : i + 1]
            avg_volume = sum(w["volume"] for w in window) / len(window)
            week["rolling_avg"] = round(avg_volume, 0)
        else:
            week["rolling_avg"] = None

    return weekly


def get_all_exercises(workouts: List[LiftingWorkout]) -> List[str]:
    """Get list of all unique exercises."""
    exercises = set()
    for workout in workouts:
        for exercise in workout.exercises:
            exercises.add(exercise.name.lower().strip())

    return sorted(list(exercises))


def calculate_advanced_lifting_stats(workouts: List[LiftingWorkout]) -> Dict:
    """Calculate comprehensive advanced lifting statistics. Filters out cardio."""
    if not workouts:
        return {}

    # Filter out cardio workouts - they're tracked via Strava
    lifting_workouts = filter_cardio_workouts(workouts)

    if not lifting_workouts:
        return {}

    # get latest bodyweight from workouts
    bodyweights = [w.bodyweight_lbs for w in lifting_workouts if w.bodyweight_lbs]
    latest_bw = bodyweights[-1] if bodyweights else 180.0

    return {
        "key_lift_prs": calculate_key_lift_prs(lifting_workouts),
        "rep_range_prs": calculate_rep_range_records(lifting_workouts, 8, 10),
        "strength_standards": calculate_strength_standards(lifting_workouts, latest_bw),
        "training_frequency": calculate_training_frequency(lifting_workouts),
        "volume_by_muscle": calculate_volume_by_muscle_group(lifting_workouts),
        "volume_trend": calculate_exercise_volume_trend(lifting_workouts),
        "all_exercises": get_all_exercises(lifting_workouts),
    }


# =============================================================================
# ADVANCED RUNNING STATISTICS
# =============================================================================


def calculate_running_streaks(activities: List[StravaActivity]) -> Dict:
    """Calculate running streak statistics."""
    runs = sorted(
        [a for a in activities if a.activity_type == ActivityType.RUN],
        key=lambda x: x.date,
    )

    if not runs:
        return {"current_streak": 0, "longest_streak": 0}

    # calculate streaks (consecutive days with runs)
    longest = 1
    current = 1

    for i in range(1, len(runs)):
        diff = (runs[i].date - runs[i - 1].date).days
        if diff == 1:
            current += 1
            longest = max(longest, current)
        elif diff > 1:
            current = 1

    # check if current streak is still active (ran today or yesterday)
    today = datetime.now().date()
    days_since_last = (today - runs[-1].date).days
    if days_since_last > 1:
        current = 0

    return {
        "current_streak": current,
        "longest_streak": longest,
        "last_run_date": runs[-1].date.isoformat() if runs else None,
    }


def calculate_pace_zones(activities: List[StravaActivity]) -> List[Dict]:
    """Categorize runs by pace zones."""
    runs = [
        a for a in activities if a.activity_type == ActivityType.RUN and a.pace_seconds
    ]

    zones = {
        "easy": {"min": 540, "max": float("inf"), "count": 0, "miles": 0},  # > 9:00
        "steady": {"min": 480, "max": 540, "count": 0, "miles": 0},  # 8:00 - 9:00
        "tempo": {"min": 420, "max": 480, "count": 0, "miles": 0},  # 7:00 - 8:00
        "threshold": {"min": 360, "max": 420, "count": 0, "miles": 0},  # 6:00 - 7:00
        "speed": {"min": 0, "max": 360, "count": 0, "miles": 0},  # < 6:00
    }

    for run in runs:
        pace = run.pace_seconds
        for zone_name, zone in zones.items():
            if zone["min"] <= pace < zone["max"]:
                zone["count"] += 1
                zone["miles"] += run.distance_miles
                break

    return [
        {
            "zone": name,
            "pace_range": _format_pace_range(z["min"], z["max"]),
            "count": z["count"],
            "miles": round(z["miles"], 1),
            "percentage": round(z["count"] / len(runs) * 100, 1) if runs else 0,
        }
        for name, z in zones.items()
    ]


def _format_pace_range(min_secs: float, max_secs: float) -> str:
    """Format pace range as string."""
    min_str = _format_pace(min_secs) if min_secs > 0 else "<6:00"
    max_str = _format_pace(max_secs) if max_secs < float("inf") else "9:00+"
    if max_secs == float("inf"):
        return f">{min_str}"
    if min_secs == 0:
        return f"<{max_str}"
    return f"{max_str} - {min_str}"


def calculate_heart_rate_stats(activities: List[StravaActivity]) -> Dict:
    """Calculate heart rate statistics from runs."""
    runs_with_hr = [
        a
        for a in activities
        if a.activity_type == ActivityType.RUN and a.average_heartrate
    ]

    if not runs_with_hr:
        return {"available": False}

    avg_hrs = [r.average_heartrate for r in runs_with_hr]
    max_hrs = [r.max_heartrate for r in runs_with_hr if r.max_heartrate]

    return {
        "available": True,
        "runs_with_hr": len(runs_with_hr),
        "avg_heartrate": round(sum(avg_hrs) / len(avg_hrs), 0),
        "highest_avg_hr": round(max(avg_hrs), 0),
        "lowest_avg_hr": round(min(avg_hrs), 0),
        "max_heartrate_ever": max(max_hrs) if max_hrs else None,
    }


def calculate_running_prs(activities: List[StravaActivity]) -> Dict:
    """Calculate personal records for running."""
    runs = [a for a in activities if a.activity_type == ActivityType.RUN]

    if not runs:
        return {}

    # filter valid runs for pace PRs (exclude zero distance)
    valid_runs = [r for r in runs if r.distance_miles > 0 and r.pace_seconds]

    prs = {}

    # fastest overall pace
    if valid_runs:
        fastest = min(valid_runs, key=lambda r: r.pace_seconds)
        prs["fastest_pace"] = {
            "name": fastest.name,
            "date": fastest.date.isoformat(),
            "pace": fastest.pace_per_mile,
            "distance_miles": fastest.distance_miles,
        }

    # longest run
    if runs:
        longest = max(runs, key=lambda r: r.distance_miles)
        prs["longest_run"] = {
            "name": longest.name,
            "date": longest.date.isoformat(),
            "distance_miles": longest.distance_miles,
            "pace": longest.pace_per_mile,
            "time_minutes": round(longest.moving_time_minutes, 1),
        }

    # most elevation gain
    if runs:
        most_climb = max(runs, key=lambda r: r.elevation_gain_feet)
        prs["most_elevation"] = {
            "name": most_climb.name,
            "date": most_climb.date.isoformat(),
            "elevation_feet": most_climb.elevation_gain_feet,
            "distance_miles": most_climb.distance_miles,
        }

    # highest suffer score (if available)
    runs_with_suffer = [r for r in runs if r.suffer_score]
    if runs_with_suffer:
        hardest = max(runs_with_suffer, key=lambda r: r.suffer_score)
        prs["hardest_effort"] = {
            "name": hardest.name,
            "date": hardest.date.isoformat(),
            "suffer_score": hardest.suffer_score,
            "distance_miles": hardest.distance_miles,
            "pace": hardest.pace_per_mile,
        }

    # fastest 5K (closest to 3.1 miles, pace extrapolated)
    five_k_runs = [r for r in valid_runs if 2.8 <= r.distance_miles <= 4.0]
    if five_k_runs:
        fastest_5k = min(five_k_runs, key=lambda r: r.pace_seconds)
        prs["fastest_5k_pace"] = {
            "name": fastest_5k.name,
            "date": fastest_5k.date.isoformat(),
            "pace": fastest_5k.pace_per_mile,
            "actual_distance": fastest_5k.distance_miles,
            "estimated_5k_time": _format_time_minutes(
                fastest_5k.pace_seconds * 3.1 / 60
            ),
        }

    return prs


def _format_time_minutes(minutes: float) -> str:
    """Format time in minutes to mm:ss."""
    mins = int(minutes)
    secs = int((minutes - mins) * 60)
    return f"{mins}:{secs:02d}"


def calculate_monthly_trends(activities: List[StravaActivity]) -> List[Dict]:
    """Calculate month-over-month running trends."""
    runs = [a for a in activities if a.activity_type == ActivityType.RUN]

    if not runs:
        return []

    monthly: Dict[str, Dict] = defaultdict(
        lambda: {
            "miles": 0.0,
            "runs": 0,
            "time_mins": 0.0,
            "elevation": 0.0,
            "paces": [],
        }
    )

    for run in runs:
        key = run.date.strftime("%Y-%m")
        monthly[key]["miles"] += run.distance_miles
        monthly[key]["runs"] += 1
        monthly[key]["time_mins"] += run.moving_time_minutes
        monthly[key]["elevation"] += run.elevation_gain_feet
        if run.pace_seconds:
            monthly[key]["paces"].append(run.pace_seconds)

    result = []
    prev_miles = None
    for month, data in sorted(monthly.items()):
        avg_pace = sum(data["paces"]) / len(data["paces"]) if data["paces"] else 0

        # calculate month-over-month change
        change = None
        if prev_miles is not None and prev_miles > 0:
            change = round((data["miles"] - prev_miles) / prev_miles * 100, 1)

        result.append(
            {
                "month": month,
                "miles": round(data["miles"], 1),
                "runs": data["runs"],
                "hours": round(data["time_mins"] / 60, 1),
                "elevation_feet": round(data["elevation"], 0),
                "avg_pace": _format_pace(avg_pace),
                "change_pct": change,
            }
        )

        prev_miles = data["miles"]

    return result


def calculate_advanced_running_stats(activities: List[StravaActivity]) -> Dict:
    """Calculate comprehensive advanced running statistics."""
    runs = [a for a in activities if a.activity_type == ActivityType.RUN]

    if not runs:
        return {}

    return {
        "total_runs": len(runs),
        "streaks": calculate_running_streaks(activities),
        "pace_zones": calculate_pace_zones(activities),
        "heart_rate_stats": calculate_heart_rate_stats(activities),
        "personal_records": calculate_running_prs(activities),
        "monthly_trends": calculate_monthly_trends(activities),
    }
