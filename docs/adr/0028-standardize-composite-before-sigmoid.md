# 0028 - Standardize the composite before the sigmoid

- **Status**: Accepted — amends [0008](0008-sigmoid-grade-mapping-parameters.md)
- **Date**: 2026-09-27

The composite is a weighted average of z-scores, so its SD is √(w′Rw).
That ranges from 0.47 (LB) to 0.99 (K) and depends on how correlated each
position's components are. The sigmoid in ADR-0008 assumes SD = 1. As a
result no LB or S has ever graded 90, and 3% of iDL have. We now divide the
composite by its SD over the **Qualified** players of that position-season
before the sigmoid, and weights are renormalized over the components a
player actually has, instead of zero-filling missing ones. A given grade
then maps to the same percentile at every position and season, which
ADR-0008 and `methodology.md` already claimed. Rankings within a
position-season are unchanged. **Provisional grades** use the pooled
per-position SD from completed seasons, because a week-3 qualified cohort
is too small to estimate it. The alternative, pooling the SD per position
across seasons, was rejected: z-scores are already within-season, so
pooling mainly preserves the 2016–17 missing-data compression.
