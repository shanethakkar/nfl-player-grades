"""Grading: component values -> 0..100 grade.

Pipeline per (season, position):
    1. Garbage-time filter applied upstream (in components/)
    2. Opponent adjustment applied upstream (in adjust/)
    3. empirical_bayes.shrink()     - shrink toward positional mean by snaps
    4. z-score within (season, position)
    5. composite.combine()          - inverse-noise weighted sum of z-scores
    6. sigmoid.to_grade()           - 100 / (1 + exp(-k * (z - z0)))

Pure functions operating on DataFrames; no DB I/O in this package.
"""
