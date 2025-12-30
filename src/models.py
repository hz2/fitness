"""Data models for workout analysis."""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List
from enum import Enum


class ActivityType(Enum):
    """Enumeration of supported activity types."""

    RUN = "run"
    WALK = "walk"
    RIDE = "ride"
    STRENGTH = "strength"
    CARDIO = "cardio"
    OTHER = "other"

    @classmethod
    def from_strava(cls, strava_type: str) -> "ActivityType":
        """Convert Strava activity type to internal type."""
        mapping = {
            "Run": cls.RUN,
            "TrailRun": cls.RUN,
            "VirtualRun": cls.RUN,
            "Walk": cls.WALK,
            "Hike": cls.WALK,
            "Ride": cls.RIDE,
            "VirtualRide": cls.RIDE,
            "WeightTraining": cls.STRENGTH,
        }
        return mapping.get(strava_type, cls.OTHER)


@dataclass
class Exercise:
    """Represents a single exercise set within a workout."""

    name: str
    weight_lbs: float
    reps: int
    rpe: Optional[float] = None

    @property
    def volume(self) -> float:
        """Calculate volume as weight × reps."""
        return self.weight_lbs * self.reps

    @classmethod
    def from_string(cls, exercise_str: str) -> Optional["Exercise"]:
        """
        Parse exercise from comma-separated string.

        Expected format: "name,weight,reps,rpe" where rpe is optional.
        """
        if not exercise_str or not exercise_str.strip():
            return None

        parts = exercise_str.split(",")
        if len(parts) < 3:
            return None

        try:
            name = parts[0].strip()
            weight = float(parts[1]) if parts[1].strip() else 0.0
            reps = int(parts[2]) if parts[2].strip() else 0
            rpe = float(parts[3]) if len(parts) > 3 and parts[3].strip() else None

            return cls(name=name, weight_lbs=weight, reps=reps, rpe=rpe)
        except (ValueError, IndexError):
            return None


@dataclass
class CardioSession:
    """Represents a cardio activity within a workout."""

    activity_type: str
    distance: Optional[float] = None
    duration_minutes: Optional[float] = None
    steps: Optional[int] = None

    @classmethod
    def from_string(cls, cardio_str: str) -> Optional["CardioSession"]:
        """Parse cardio session from comma-separated string."""
        if not cardio_str or not cardio_str.strip():
            return None

        parts = cardio_str.split(",")
        if len(parts) < 2:
            return None

        try:
            activity_type = parts[0].strip()
            session = cls(activity_type=activity_type)

            # parse distance or steps
            if len(parts) >= 2 and parts[1].strip():
                val = parts[1].strip()
                if "." in val:
                    session.distance = float(val)
                else:
                    session.steps = int(val)

            # parse duration
            if len(parts) >= 3 and parts[2].strip():
                time_str = parts[2].strip()
                if ":" in time_str:
                    mins, secs = time_str.split(":")
                    session.duration_minutes = int(mins) + int(secs) / 60
                else:
                    session.duration_minutes = float(time_str)

            return session
        except (ValueError, IndexError):
            return None


@dataclass
class LiftingWorkout:
    """Represents a strength training session."""

    date: date
    muscle_groups: str
    exercises: List[Exercise] = field(default_factory=list)
    cardio: Optional[CardioSession] = None
    pushups: Optional[int] = None
    pullups: Optional[int] = None
    bodyweight_lbs: Optional[float] = None
    notes: Optional[str] = None

    @property
    def total_volume(self) -> float:
        """Calculate total volume across all exercises."""
        return sum(e.volume for e in self.exercises)

    @property
    def exercise_count(self) -> int:
        """Count of exercises in this workout."""
        return len(self.exercises)


@dataclass
class StravaActivity:
    """Represents an activity from Strava."""

    id: int
    name: str
    activity_type: ActivityType
    sport_type: str
    date: date
    start_time: datetime
    distance_miles: float
    distance_meters: float
    moving_time_seconds: int
    elapsed_time_seconds: int
    elevation_gain_feet: float
    elevation_gain_meters: float
    average_speed_mph: float
    max_speed_mph: float
    average_heartrate: Optional[float] = None
    max_heartrate: Optional[int] = None
    average_cadence: Optional[float] = None
    calories: Optional[int] = None
    suffer_score: Optional[int] = None
    polyline: Optional[str] = None

    @property
    def moving_time_minutes(self) -> float:
        """Moving time converted to minutes."""
        return self.moving_time_seconds / 60

    @property
    def pace_per_mile(self) -> Optional[str]:
        """Calculate pace as min:sec per mile."""
        if self.distance_miles == 0:
            return None

        pace_seconds = self.moving_time_seconds / self.distance_miles
        minutes = int(pace_seconds // 60)
        seconds = int(pace_seconds % 60)
        return f"{minutes}:{seconds:02d}"

    @property
    def pace_seconds(self) -> Optional[float]:
        """Pace in seconds per mile for calculations."""
        if self.distance_miles == 0:
            return None
        return self.moving_time_seconds / self.distance_miles

    @classmethod
    def from_strava_api(cls, data: dict) -> "StravaActivity":
        """
        Create StravaActivity from Strava API response.
        """
        return cls(
            id=data["id"],
            name=data["name"],
            activity_type=ActivityType.from_strava(data["type"]),
            sport_type=data.get("sport_type", data["type"]),
            date=datetime.fromisoformat(
                data["start_date_local"].replace("Z", "+00:00")
            ).date(),
            start_time=datetime.fromisoformat(
                data["start_date_local"].replace("Z", "+00:00")
            ),
            distance_miles=round(data.get("distance", 0) / 1609.34, 2),
            distance_meters=data.get("distance", 0),
            moving_time_seconds=data.get("moving_time", 0),
            elapsed_time_seconds=data.get("elapsed_time", 0),
            elevation_gain_feet=round(data.get("total_elevation_gain", 0) * 3.281, 1),
            elevation_gain_meters=data.get("total_elevation_gain", 0),
            average_speed_mph=round(data.get("average_speed", 0) * 2.237, 2),
            max_speed_mph=round(data.get("max_speed", 0) * 2.237, 2),
            average_heartrate=data.get("average_heartrate"),
            max_heartrate=data.get("max_heartrate"),
            average_cadence=data.get("average_cadence"),
            calories=data.get("calories"),
            suffer_score=data.get("suffer_score"),
            polyline=data.get("map", {}).get("summary_polyline"),
        )


@dataclass
class RunningStats:
    """Aggregated running statistics."""

    total_runs: int
    total_miles: float
    total_time_hours: float
    total_elevation_feet: float
    avg_distance: float
    avg_pace: str
    fastest_pace: str
    longest_run_miles: float
    runs_this_month: int
    miles_this_month: float
    fastest_run: Optional[dict] = None
    longest_run: Optional[dict] = None


@dataclass
class LiftingStats:
    """Aggregated lifting statistics."""

    total_workouts: int
    total_volume_lbs: float
    workout_distribution: dict
    date_range_start: date
    date_range_end: date
    personal_records: List[dict] = field(default_factory=list)
