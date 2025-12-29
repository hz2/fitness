#!/usr/bin/env python
"""
Workout analysis CLI runner.

Usage:
    python run.py fetch     # fetch fresh data from strava
    python run.py export    # export to hugo site
    python run.py analyze   # show summary stats
    python run.py visualize # generate charts
    python run.py auth      # run strava oauth flow
    python run.py all       # full pipeline
"""

import sys
from pathlib import Path

# add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.main import main

if __name__ == "__main__":
    main()
