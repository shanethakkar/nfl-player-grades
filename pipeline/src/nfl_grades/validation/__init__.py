"""Validation suite run on every grading rebuild.

Modules:
    face_validity  - top 10 at each position; print for human review
    reliability    - year-over-year correlation per position/component
    predictive     - this-year grades predicting next-year player/team outcomes
    benchmarks     - correlation with Pro Bowls, All-Pros, public top-100 lists

Each writes a report under `pipeline/reports/<date>/` (gitignored) and prints
a summary to stdout. Fails the build if any hard threshold is violated.
"""
