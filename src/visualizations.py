"""
Workout data visualization.

Provides functions for creating charts and maps from workout data.
Uses matplotlib for static charts and folium for interactive maps.
"""

import logging
from pathlib import Path
from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np

from .models import StravaActivity, LiftingWorkout, ActivityType
from .analyzer import (
    calculate_weekly_mileage,
    calculate_monthly_mileage,
    calculate_weekly_volume,
    calculate_lifting_stats,
)


logger = logging.getLogger(__name__)

# plot styling
plt.style.use("seaborn-v0_8-whitegrid")
COLORS = {
    "primary": "#2563eb",
    "secondary": "#64748b",
    "accent": "#f59e0b",
    "success": "#10b981",
}


def plot_weekly_mileage(
    activities: List[StravaActivity],
    output_path: Optional[Path] = None,
    show: bool = True,
) -> None:
    """
    Plot weekly running mileage over time.

    Parameters:
        activities: List of Strava activities.
        output_path: Optional path to save the figure.
        show: Whether to display the plot.
    """
    data = calculate_weekly_mileage(activities)

    if not data:
        logger.warning("No mileage data to plot")
        return

    fig, ax = plt.subplots(figsize=(14, 6))

    x = range(len(data))
    miles = [d["miles"] for d in data]

    ax.bar(x, miles, color=COLORS["primary"], alpha=0.8, label="Weekly miles")
    ax.plot(x, miles, "o-", color=COLORS["accent"], markersize=4, linewidth=1)

    ax.set_xlabel("Week", fontsize=11)
    ax.set_ylabel("Miles", fontsize=11)
    ax.set_title("Weekly Running Mileage", fontsize=14, fontweight="bold")

    # x-axis labels (show every nth label to avoid crowding)
    step = max(1, len(data) // 12)
    labels = [d["date"][:10] if d["date"] else "" for d in data]
    ax.set_xticks(range(0, len(data), step))
    ax.set_xticklabels(labels[::step], rotation=45, ha="right")

    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved plot to {output_path}")

    if show:
        plt.show()
    else:
        plt.close()


def plot_pace_distribution(
    activities: List[StravaActivity],
    output_path: Optional[Path] = None,
    show: bool = True,
) -> None:
    """
    Plot distribution of running paces.

    Parameters:
        activities: List of Strava activities.
        output_path: Optional path to save the figure.
        show: Whether to display the plot.
    """
    runs = [a for a in activities if a.activity_type == ActivityType.RUN]
    paces = [r.pace_seconds / 60 for r in runs if r.pace_seconds]

    if not paces:
        logger.warning("No pace data to plot")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.hist(paces, bins=20, color=COLORS["primary"], edgecolor="white", alpha=0.8)

    avg_pace = sum(paces) / len(paces)
    ax.axvline(
        avg_pace,
        color=COLORS["accent"],
        linestyle="--",
        linewidth=2,
        label=f"Average: {avg_pace:.1f} min/mi",
    )

    ax.set_xlabel("Pace (min/mile)", fontsize=11)
    ax.set_ylabel("Number of Runs", fontsize=11)
    ax.set_title("Pace Distribution", fontsize=14, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close()


def plot_monthly_summary(
    activities: List[StravaActivity],
    output_path: Optional[Path] = None,
    show: bool = True,
) -> None:
    """
    Plot monthly running summary with miles and run count.

    Parameters:
        activities: List of Strava activities.
        output_path: Optional path to save the figure.
        show: Whether to display the plot.
    """
    data = calculate_monthly_mileage(activities)

    if not data:
        logger.warning("No monthly data to plot")
        return

    fig, ax1 = plt.subplots(figsize=(12, 6))

    x = range(len(data))
    miles = [d["miles"] for d in data]
    runs = [d["runs"] for d in data]

    bars = ax1.bar(x, miles, color=COLORS["primary"], alpha=0.8)
    ax1.set_xlabel("Month", fontsize=11)
    ax1.set_ylabel("Miles", color=COLORS["primary"], fontsize=11)
    ax1.tick_params(axis="y", labelcolor=COLORS["primary"])

    ax2 = ax1.twinx()
    ax2.plot(x, runs, "o-", color=COLORS["accent"], linewidth=2, markersize=8)
    ax2.set_ylabel("Number of Runs", color=COLORS["accent"], fontsize=11)
    ax2.tick_params(axis="y", labelcolor=COLORS["accent"])

    months = [d["month"] for d in data]
    ax1.set_xticks(x)
    ax1.set_xticklabels(months, rotation=45, ha="right")
    ax1.set_title("Monthly Running Summary", fontsize=14, fontweight="bold")

    # add value labels on bars
    for bar, val in zip(bars, miles):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1,
            f"{val:.0f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close()


def plot_distance_vs_pace(
    activities: List[StravaActivity],
    output_path: Optional[Path] = None,
    show: bool = True,
) -> None:
    """
    Scatter plot of distance vs pace colored by elevation.

    Parameters:
        activities: List of Strava activities.
        output_path: Optional path to save the figure.
        show: Whether to display the plot.
    """
    runs = [
        a for a in activities if a.activity_type == ActivityType.RUN and a.pace_seconds
    ]

    if not runs:
        logger.warning("No run data to plot")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    distances = [r.distance_miles for r in runs]
    paces = [r.pace_seconds / 60 for r in runs]
    elevations = [r.elevation_gain_feet for r in runs]

    scatter = ax.scatter(distances, paces, c=elevations, cmap="YlOrRd", alpha=0.7, s=60)

    plt.colorbar(scatter, label="Elevation Gain (ft)")

    ax.set_xlabel("Distance (miles)", fontsize=11)
    ax.set_ylabel("Pace (min/mile)", fontsize=11)
    ax.set_title(
        "Distance vs Pace (colored by elevation)", fontsize=14, fontweight="bold"
    )
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close()


def plot_weekly_lifting_volume(
    workouts: List[LiftingWorkout],
    output_path: Optional[Path] = None,
    show: bool = True,
) -> None:
    """
    Plot weekly lifting volume over time.

    Parameters:
        workouts: List of lifting workouts.
        output_path: Optional path to save the figure.
        show: Whether to display the plot.
    """
    data = calculate_weekly_volume(workouts)

    if not data:
        logger.warning("No volume data to plot")
        return

    fig, ax = plt.subplots(figsize=(12, 6))

    x = range(len(data))
    volumes = [d["volume"] for d in data]

    ax.bar(x, volumes, color=COLORS["success"], alpha=0.8)

    ax.set_xlabel("Week", fontsize=11)
    ax.set_ylabel("Volume (lbs)", fontsize=11)
    ax.set_title("Weekly Lifting Volume", fontsize=14, fontweight="bold")

    labels = [d["date"][:10] if d["date"] else "" for d in data]
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")

    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close()


def plot_workout_distribution(
    workouts: List[LiftingWorkout],
    output_path: Optional[Path] = None,
    show: bool = True,
) -> None:
    """
    Pie chart of workout distribution by muscle group.

    Parameters:
        workouts: List of lifting workouts.
        output_path: Optional path to save the figure.
        show: Whether to display the plot.
    """
    stats = calculate_lifting_stats(workouts)

    if not stats.workout_distribution:
        logger.warning("No distribution data to plot")
        return

    fig, ax = plt.subplots(figsize=(8, 8))

    labels = list(stats.workout_distribution.keys())
    sizes = list(stats.workout_distribution.values())

    colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))

    ax.pie(sizes, labels=labels, autopct="%1.1f%%", colors=colors, startangle=90)
    ax.set_title("Workout Distribution by Muscle Group", fontsize=14, fontweight="bold")

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close()


def create_runs_map(
    activities: List[StravaActivity],
    strava_client,
    num_runs: int = 15,
    output_path: Optional[Path] = None,
):
    """
    Create interactive map with recent run routes.

    Parameters:
        activities: List of Strava activities.
        strava_client: Authenticated Strava client.
        num_runs: Number of recent runs to include.
        output_path: Optional path to save HTML map.

    Returns:
        folium.Map: Interactive map object.
    """
    try:
        import folium
        import polyline
    except ImportError:
        logger.error("folium and polyline required for maps")
        return None

    runs = [a for a in activities if a.activity_type == ActivityType.RUN][:num_runs]

    if not runs:
        logger.warning("No runs to map")
        return None

    # fetch polylines for each run
    routes = []
    for run in runs:
        try:
            details = strava_client.fetch_activity_details(run.id)
            poly = details.get("map", {}).get("summary_polyline")
            if poly:
                coords = polyline.decode(poly)
                routes.append(
                    {
                        "name": run.name,
                        "date": run.date,
                        "coords": coords,
                        "distance": run.distance_miles,
                        "pace": run.pace_per_mile,
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to fetch route for {run.name}: {e}")

    if not routes:
        logger.warning("No routes found")
        return None

    # create map centered on first route
    center = routes[0]["coords"][len(routes[0]["coords"]) // 2]
    m = folium.Map(location=center, zoom_start=13, tiles="CartoDB positron")

    # color palette for routes
    colors = [
        "#e41a1c",
        "#377eb8",
        "#4daf4a",
        "#984ea3",
        "#ff7f00",
        "#ffff33",
        "#a65628",
        "#f781bf",
        "#999999",
        "#66c2a5",
    ]

    for i, route in enumerate(routes):
        color = colors[i % len(colors)]

        folium.PolyLine(
            route["coords"],
            color=color,
            weight=3,
            opacity=0.8,
            popup=(
                f"{route['name']}<br>"
                f"{route['date']}<br>"
                f"{route['distance']} mi @ {route['pace']}/mi"
            ),
        ).add_to(m)

        folium.CircleMarker(
            route["coords"][0],
            radius=6,
            color=color,
            fill=True,
            popup=f"Start: {route['name']}",
        ).add_to(m)

    if output_path:
        m.save(str(output_path))
        logger.info(f"Saved map to {output_path}")

    return m
