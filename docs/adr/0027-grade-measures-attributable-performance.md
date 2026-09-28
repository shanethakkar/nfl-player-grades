# 0027 - A grade measures attributable season performance

- **Status**: Accepted
- **Date**: 2026-09-27

A **Grade** describes how well a player performed *this season*, counting
only what the player controls. It is not season production with context
included, and it is not a talent forecast. We chose it over production
because the
[2026-09-27 system audit](../grading/audits/2026-09-27-system-audit.md)
showed QB/WR/TE/CB grades lose almost all year-over-year persistence when a
player changes teams (r ≈ 0.39 stayers vs 0.18 changers, pooled). Much of
the current grade is QB, scheme and team. We chose it over a talent
estimate because a season description is what a weekly-updated,
per-season grade can honestly claim. Consequences: **Portability** and
within-season **Reliability** become primary evaluation criteria, replacing
next-year Pro Bowl selection (see [0029](0029-reputation-free-evaluation.md)).
Components dominated by team context get residualized or down-weighted
instead of being kept under the old "context-dependent skill" exception.
