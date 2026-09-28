"""Grading: component values -> 0..100 grade.

Pipeline per (season, position):
    1. Garbage-time filter applied upstream (in components/)
    2. Opponent adjustment applied upstream (in adjust/)
    3. empirical_bayes.shrink()     - shrink toward positional mean by snaps
    4. z-score within (season, position)
    5. scoring.score()              - shared by every grader, preview, regrade:
         composite.combine()        - weighted sum of Component z-scores,
                                      renormalized over those present
         standardize                - divide by the qualified cohort's SD
         sigmoid.to_grade()         - 100 / (1 + exp(-k * (z - z0)))
         percentile                 - within the qualified cohort

Pure functions operating on DataFrames; no DB I/O in this package.
"""
