"""
Main entry point for workout analysis.

Provides CLI interface for fetching data from sources, running
analysis, generating visualizations, and exporting to Hugo.
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from typing import List, Optional

from .config import AppConfig
from .models import StravaActivity, LiftingWorkout
from .strava_client import StravaClient, run_oauth_flow, save_activities_to_json
from .sheets_client import load_workouts_from_file
from .analyzer import calculate_running_stats, calculate_lifting_stats
from .hugo_exporter import HugoExporter
from .visualizations import (
    plot_weekly_mileage,
    plot_pace_distribution,
    plot_monthly_summary,
    plot_distance_vs_pace,
    plot_weekly_lifting_volume,
    plot_workout_distribution,
    create_runs_map,
)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_strava_activities(
    config: AppConfig, cache_path: Optional[Path] = None, force_refresh: bool = False
) -> List[StravaActivity]:
    """
    Load Strava activities, using cache if available.

    Parameters:
        config: Application configuration.
        cache_path: Path to cache file.
        force_refresh: Force fetch from API even if cache exists.

    Returns:
        List of Strava activities.
    """
    if cache_path is None:
        cache_path = config.paths.data_dir / "strava_activities.json"

    # use cache if available and not forcing refresh
    if cache_path.exists() and not force_refresh:
        logger.info(f"Loading cached activities from {cache_path}")
        with open(cache_path) as f:
            data = json.load(f)
        return [
            StravaActivity.from_strava_api(_convert_cache_to_api(item)) for item in data
        ]

    # fetch from API
    if config.strava is None:
        logger.error("Strava not configured. Run 'auth' command first.")
        return []

    logger.info("Fetching activities from Strava API...")
    client = StravaClient(config.strava)
    activities = list(client.fetch_all_activities())

    # save to cache
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    save_activities_to_json(activities, cache_path)

    return activities


def _convert_cache_to_api(item: dict) -> dict:
    """
    Convert cached activity format back to API format for parsing.

    Parameters:
        item: Cached activity dictionary.

    Returns:
        Dictionary in Strava API format.
    """
    return {
        "id": item["id"],
        "name": item["name"],
        "type": item.get("sport_type", item.get("type", "Other")),
        "sport_type": item.get("sport_type", item.get("type", "Other")),
        "start_date_local": item["start_time"],
        "distance": item["distance_meters"],
        "moving_time": item["moving_time_seconds"],
        "elapsed_time": item["elapsed_time_seconds"],
        "total_elevation_gain": item["elevation_gain_meters"],
        "average_speed": item["average_speed_mph"] / 2.237,
        "max_speed": item["max_speed_mph"] / 2.237,
        "average_heartrate": item.get("average_heartrate"),
        "max_heartrate": item.get("max_heartrate"),
        "average_cadence": item.get("average_cadence"),
        "calories": item.get("calories"),
        "suffer_score": item.get("suffer_score"),
    }


def load_lifting_workouts(
    config: AppConfig, filepath: Optional[Path] = None
) -> List[LiftingWorkout]:
    """
    Load lifting workouts from TSV file.

    Parameters:
        config: Application configuration.
        filepath: Path to workout file.

    Returns:
        List of lifting workouts.
    """
    if filepath is None:
        filepath = config.paths.data_dir / "workouts.tsv"

    if not filepath.exists():
        # check parent directory
        alt_path = config.paths.base_dir / "workouts.tsv"
        if alt_path.exists():
            filepath = alt_path
        else:
            logger.warning(f"Workout file not found: {filepath}")
            return []

    return load_workouts_from_file(filepath)


def print_summary(
    activities: List[StravaActivity], workouts: List[LiftingWorkout]
) -> None:
    """
    Print summary of all workout data.

    Parameters:
        activities: List of Strava activities.
        workouts: List of lifting workouts.
    """
    print("\n" + "=" * 60)
    print("WORKOUT SUMMARY")
    print("=" * 60)

    if activities:
        stats = calculate_running_stats(activities)
        print("\n📍 RUNNING")
        print(f"   Total runs: {stats.total_runs}")
        print(f"   Total miles: {stats.total_miles}")
        print(f"   Total time: {stats.total_time_hours} hours")
        print(f"   Avg pace: {stats.avg_pace}/mi")
        print(f"   Fastest pace: {stats.fastest_pace}/mi")
        print(
            f"   This month: {stats.runs_this_month} runs, "
            f"{stats.miles_this_month} miles"
        )

        if stats.fastest_run:
            print(f"\n   Fastest: {stats.fastest_run['name']}")
            print(
                f"            {stats.fastest_run['pace']}/mi on "
                f"{stats.fastest_run['date']}"
            )

        if stats.longest_run:
            print(f"\n   Longest: {stats.longest_run['name']}")
            print(
                f"            {stats.longest_run['distance']} mi on "
                f"{stats.longest_run['date']}"
            )

    if workouts:
        stats = calculate_lifting_stats(workouts)
        print("\n🏋️  LIFTING")
        print(f"   Total workouts: {stats.total_workouts}")
        print(f"   Total volume: {stats.total_volume_lbs:,.0f} lbs")
        print(f"   Date range: {stats.date_range_start} to " f"{stats.date_range_end}")

        print("\n   Distribution:")
        for group, count in stats.workout_distribution.items():
            print(f"     {group}: {count}")

        if stats.personal_records:
            print("\n   Top PRs:")
            for pr in stats.personal_records[:5]:
                if pr["max_weight"] > 0:
                    print(f"     {pr['exercise']}: {pr['max_weight']} lbs")

    print("\n" + "=" * 60)


def cmd_fetch(args: argparse.Namespace, config: AppConfig) -> None:
    """Fetch data from sources."""
    if args.source in ("strava", "all"):
        load_strava_activities(config, force_refresh=True)
        logger.info("Strava data fetched and cached")


def cmd_export(args: argparse.Namespace, config: AppConfig) -> None:
    """Export data to Hugo site or custom output directory."""
    activities = load_strava_activities(config)
    workouts = load_lifting_workouts(config)

    # Use custom output dir if specified, otherwise use Hugo data dir
    if hasattr(args, "output") and args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        exporter = HugoExporter(output_dir, output_dir)
        logger.info(f"Exporting to custom directory: {output_dir}")
    else:
        exporter = HugoExporter(
            config.paths.hugo_data_dir, config.paths.hugo_content_dir
        )
        logger.info(f"Exporting to Hugo site: {config.paths.hugo_data_dir}")

    exporter.export_all(activities, workouts)


def cmd_analyze(args: argparse.Namespace, config: AppConfig) -> None:
    """Analyze workout data and show summary."""
    activities = load_strava_activities(config)
    workouts = load_lifting_workouts(config)
    print_summary(activities, workouts)


def cmd_visualize(args: argparse.Namespace, config: AppConfig) -> None:
    """Generate visualizations."""
    activities = load_strava_activities(config)
    workouts = load_lifting_workouts(config)

    output_dir = config.paths.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    show = not args.no_show

    if activities:
        logger.info("Generating running visualizations...")
        plot_weekly_mileage(activities, output_dir / "weekly_mileage.png", show)
        plot_pace_distribution(activities, output_dir / "pace_dist.png", show)
        plot_monthly_summary(activities, output_dir / "monthly.png", show)
        plot_distance_vs_pace(activities, output_dir / "dist_pace.png", show)

        if not args.no_map and config.strava:
            logger.info("Creating run map...")
            client = StravaClient(config.strava)
            create_runs_map(
                activities,
                client,
                num_runs=15,
                output_path=output_dir / "runs_map.html",
            )

    if workouts:
        logger.info("Generating lifting visualizations...")
        plot_weekly_lifting_volume(workouts, output_dir / "weekly_volume.png", show)
        plot_workout_distribution(workouts, output_dir / "workout_dist.png", show)


def cmd_auth(args: argparse.Namespace, config: AppConfig) -> None:
    """Run Strava OAuth flow."""
    if config.strava is None:
        print("Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env first")
        return

    run_oauth_flow(config.strava)


def cmd_all(args: argparse.Namespace, config: AppConfig) -> None:
    """Run full pipeline: fetch, analyze, export."""
    logger.info("Running full pipeline...")

    # fetch fresh data
    activities = load_strava_activities(config, force_refresh=True)
    workouts = load_lifting_workouts(config)

    # show summary
    print_summary(activities, workouts)

    # export to hugo
    exporter = HugoExporter(config.paths.hugo_data_dir, config.paths.hugo_content_dir)
    exporter.export_all(activities, workouts)

    logger.info("Pipeline complete!")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Workout data analysis and Hugo export"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch data from sources")
    fetch_parser.add_argument(
        "--source",
        choices=["strava", "all"],
        default="all",
        help="Data source to fetch",
    )

    # export command
    export_parser = subparsers.add_parser("export", help="Export data to Hugo site")
    export_parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Custom output directory (default: Hugo data dir)",
    )

    # analyze command
    subparsers.add_parser("analyze", help="Show workout summary")

    # visualize command
    viz_parser = subparsers.add_parser("visualize", help="Generate charts")
    viz_parser.add_argument(
        "--no-show", action="store_true", help="Save plots without displaying"
    )
    viz_parser.add_argument("--no-map", action="store_true", help="Skip map generation")

    # auth command
    subparsers.add_parser("auth", help="Run Strava OAuth flow")

    # all command
    subparsers.add_parser("all", help="Run full pipeline")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    config = AppConfig.load()

    commands = {
        "fetch": cmd_fetch,
        "export": cmd_export,
        "analyze": cmd_analyze,
        "visualize": cmd_visualize,
        "auth": cmd_auth,
        "all": cmd_all,
    }

    commands[args.command](args, config)


if __name__ == "__main__":
    main()
