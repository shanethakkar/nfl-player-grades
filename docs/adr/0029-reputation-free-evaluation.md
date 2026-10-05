# 0029 - Reputation-free evaluation with a hold-out; opponent adjustment only as a tested candidate

- **Status**: Accepted — supersedes the Pro Bowl validity gate in `docs/grading/audit-playbook.md`
- **Date**: 2026-09-27

Formula changes ship on three criteria:
- within-season **Reliability** (odd/even weeks);
- **Portability** (YoY for team changers);
- next-season prediction.

Each is fit on 2016–2022 and judged on a 2023–2025 hold-out. Next-year Pro
Bowl selection is demoted to a same-season, position-matched face-validity
check. The audit found that its standard error (0.03–0.07) swamps the
+0.005–0.02 deltas used to justify past changes. It also found label bugs,
and no hold-out had ever been run.

**Opponent adjustment** was measured directly. It moves RB/WR/TE/CB/EDGE
grades by under 1.2 points on average, with Spearman ≥ 0.996 against the
unadjusted grades. It does not improve rest-of-season prediction in-season,
even with oracle defense ratings. It is therefore not applied in-season or
at those positions. QB full-season adjustment (+0.022 YoY, mean 1.5 pts)
stays a **Candidate**, and ships only if it wins on the hold-out.

**Implementation** (#12): `nflgrades evaluate` (`grading/evaluation.py`,
`grading/panels.py`) and the ship rule in `docs/grading/audit-playbook.md`.
The Pro Bowl report (`nflgrades validity`) is same-season and joins on name
and position group (#5).
