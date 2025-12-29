"""
Tests for workout analysis models.

Tests parsing functions and model properties.
"""

import pytest
from datetime import date, datetime

from src.models import (
    Exercise,
    CardioSession,
    LiftingWorkout,
    StravaActivity,
    ActivityType,
)


class TestExercise:
    """Tests for Exercise model."""

    def test_from_string_valid(self):
        """Test parsing valid exercise string."""
        result = Exercise.from_string("bench press,135,10,8")

        assert result is not None
        assert result.name == "bench press"
        assert result.weight_lbs == 135.0
        assert result.reps == 10
        assert result.rpe == 8.0

    def test_from_string_no_rpe(self):
        """Test parsing exercise without RPE."""
        result = Exercise.from_string("squat,225,5")

        assert result is not None
        assert result.name == "squat"
        assert result.weight_lbs == 225.0
        assert result.reps == 5
        assert result.rpe is None

    def test_from_string_empty(self):
        """Test parsing empty string returns None."""
        assert Exercise.from_string("") is None
        assert Exercise.from_string("   ") is None
        assert Exercise.from_string(None) is None

    def test_from_string_invalid(self):
        """Test parsing invalid string returns None."""
        assert Exercise.from_string("just-name") is None
        assert Exercise.from_string("name,weight") is None

    def test_volume_calculation(self):
        """Test volume property calculates correctly."""
        exercise = Exercise(name="test", weight_lbs=100, reps=10)
        assert exercise.volume == 1000


class TestCardioSession:
    """Tests for CardioSession model."""

    def test_from_string_with_distance(self):
        """Test parsing cardio with distance."""
        result = CardioSession.from_string("walk,1.5,30")

        assert result is not None
        assert result.activity_type == "walk"
        assert result.distance == 1.5
        assert result.duration_minutes == 30.0

    def test_from_string_with_steps(self):
        """Test parsing cardio with steps."""
        result = CardioSession.from_string("stair master,2500,45")

        assert result is not None
        assert result.activity_type == "stair master"
        assert result.steps == 2500
        assert result.duration_minutes == 45.0

    def test_from_string_time_format(self):
        """Test parsing cardio with mm:ss time format."""
        result = CardioSession.from_string("run,3.0,25:30")

        assert result is not None
        assert result.duration_minutes == pytest.approx(25.5, rel=0.01)

    def test_from_string_empty(self):
        """Test parsing empty string returns None."""
        assert CardioSession.from_string("") is None
        assert CardioSession.from_string(None) is None


class TestLiftingWorkout:
    """Tests for LiftingWorkout model."""

    def test_total_volume(self):
        """Test total volume calculation across exercises."""
        workout = LiftingWorkout(
            date=date(2024, 1, 1),
            muscle_groups="Push",
            exercises=[
                Exercise(name="bench", weight_lbs=135, reps=10),
                Exercise(name="ohp", weight_lbs=95, reps=8),
            ],
        )

        expected = (135 * 10) + (95 * 8)
        assert workout.total_volume == expected

    def test_exercise_count(self):
        """Test exercise count property."""
        workout = LiftingWorkout(
            date=date(2024, 1, 1),
            muscle_groups="Legs",
            exercises=[
                Exercise(name="squat", weight_lbs=225, reps=5),
                Exercise(name="rdl", weight_lbs=185, reps=8),
                Exercise(name="leg press", weight_lbs=270, reps=10),
            ],
        )

        assert workout.exercise_count == 3


class TestActivityType:
    """Tests for ActivityType enum."""

    def test_from_strava_run(self):
        """Test mapping Strava run types."""
        assert ActivityType.from_strava("Run") == ActivityType.RUN
        assert ActivityType.from_strava("TrailRun") == ActivityType.RUN
        assert ActivityType.from_strava("VirtualRun") == ActivityType.RUN

    def test_from_strava_walk(self):
        """Test mapping Strava walk types."""
        assert ActivityType.from_strava("Walk") == ActivityType.WALK
        assert ActivityType.from_strava("Hike") == ActivityType.WALK

    def test_from_strava_unknown(self):
        """Test unknown types map to OTHER."""
        assert ActivityType.from_strava("Yoga") == ActivityType.OTHER
        assert ActivityType.from_strava("Unknown") == ActivityType.OTHER


class TestStravaActivity:
    """Tests for StravaActivity model."""

    def test_pace_per_mile(self):
        """Test pace calculation."""
        activity = StravaActivity(
            id=1,
            name="Test Run",
            activity_type=ActivityType.RUN,
            sport_type="Run",
            date=date(2024, 1, 1),
            start_time=datetime(2024, 1, 1, 8, 0),
            distance_miles=3.0,
            distance_meters=4828.0,
            moving_time_seconds=1800,  # 30 min = 10:00/mi
            elapsed_time_seconds=1800,
            elevation_gain_feet=0,
            elevation_gain_meters=0,
            average_speed_mph=6.0,
            max_speed_mph=8.0,
        )

        assert activity.pace_per_mile == "10:00"

    def test_pace_zero_distance(self):
        """Test pace returns None for zero distance."""
        activity = StravaActivity(
            id=1,
            name="Test",
            activity_type=ActivityType.RUN,
            sport_type="Run",
            date=date(2024, 1, 1),
            start_time=datetime(2024, 1, 1, 8, 0),
            distance_miles=0,
            distance_meters=0,
            moving_time_seconds=1800,
            elapsed_time_seconds=1800,
            elevation_gain_feet=0,
            elevation_gain_meters=0,
            average_speed_mph=0,
            max_speed_mph=0,
        )

        assert activity.pace_per_mile is None

    def test_moving_time_minutes(self):
        """Test moving time conversion to minutes."""
        activity = StravaActivity(
            id=1,
            name="Test",
            activity_type=ActivityType.RUN,
            sport_type="Run",
            date=date(2024, 1, 1),
            start_time=datetime(2024, 1, 1, 8, 0),
            distance_miles=1.0,
            distance_meters=1609.0,
            moving_time_seconds=600,  # 10 minutes
            elapsed_time_seconds=600,
            elevation_gain_feet=0,
            elevation_gain_meters=0,
            average_speed_mph=6.0,
            max_speed_mph=6.0,
        )

        assert activity.moving_time_minutes == 10.0
