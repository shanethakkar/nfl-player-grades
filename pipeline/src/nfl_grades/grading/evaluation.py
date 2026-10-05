"""Reputation-free evaluation harness for Formulas (ADR-0029).

Scores the current or a proposed Formula, including ones with Candidate
Components, on:

- **Reliability**: odd-week vs even-week Composite correlation, stepped
  up to a full season with Spearman-Brown.
- **Portability**: Composite YoY for players who changed teams.
- **Next-season prediction**: Composite in N vs Composite in N+1 (``yoy``)
  and vs the position's primary Component in N+1 (``next_primary``).
- **Face validity** (reported, never gating): same-season Pro Bowl r.

Each metric is reported separately for a 2016-2022 fit window and a
2023-2025 hold-out. A window only ever sees its own seasons: YoY pairs
that straddle the split belong to neither. A proposed Formula gets paired
deltas against the current one with a player-clustered bootstrap CI;
:func:`ship_rule` applies the hold-out ship rule to them.

Correlations use the standardized Composite, not the 0-100 Grade: the
sigmoid is monotonic, and the Composite keeps the tails linear.

Pure: DataFrames in, results out. ``grading.panels`` builds the inputs
from the database and ``nflgrades evaluate`` prints the report.

Inputs:

- ``panel``: long Component values, one row per (player_id, season,
  split, component) with ``raw`` (unshrunk rate) and ``n`` (its sample
  size). ``split`` is ``full``, ``odd`` or ``even`` (week parity).
- ``roster``: one row per (player_id, season) with ``team`` and
  ``qualified`` (full-season Qualified). Only Qualified players are
  scored, in every split, so the halves compare the same cohort.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, TypeVar

import numpy as np
import pandas as pd
from scipy.stats import norm

from nfl_grades.grading import empirical_bayes, scoring, zscore

WINDOWS: Final[dict[str, range]] = {
    "fit": range(2016, 2023),
    "holdout": range(2023, 2026),
}

SPLITS: Final[tuple[str, ...]] = ("full", "odd", "even")

METRIC_LABELS: Final[dict[str, str]] = {
    "reliability": "Reliability (odd/even, S-B)",
    "portability": "Portability (changers YoY)",
    "yoy": "YoY, all (grade N -> N+1)",
    "yoy_stayers": "YoY, stayers",
    "next_primary": "Grade N -> primary N+1",
    "pro_bowl": "Pro Bowl r (face validity)",
}

# Ship rule (docs/grading/audit-playbook.md): neither of these may fall
# beyond noise, and at least one IMPROVEMENT_METRICS must rise with a CI
# excluding zero.
GUARDED_METRICS: Final[tuple[str, ...]] = ("reliability", "portability")
IMPROVEMENT_METRICS: Final[tuple[str, ...]] = ("reliability", "portability", "yoy", "next_primary")

# A correlation, or an array of bootstrap correlations.
R = TypeVar("R", float, np.ndarray)

_KEYS = ["player_id", "season"]
_MIN_PAIRS = 4


@dataclass(frozen=True)
class Formula:
    """Signed Component weights plus each Component's shrinkage k."""

    weights: Mapping[str, float]
    shrinkage_k: Mapping[str, float]


@dataclass(frozen=True)
class Estimate:
    value: float
    lo: float
    hi: float
    n: int


@dataclass(frozen=True)
class WindowReport:
    """Metrics for one window. ``proposed`` and ``delta`` (proposed minus
    current, paired) are None when no proposed Formula was given."""

    name: str
    seasons: range
    current: dict[str, Estimate]
    proposed: dict[str, Estimate] | None
    delta: dict[str, Estimate] | None


@dataclass(frozen=True)
class ShipVerdict:
    passes: bool
    reasons: tuple[str, ...]


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def spearman_brown(r: R, factor: float = 2.0) -> R:
    """Reliability of a measure ``factor`` times as long as one with
    reliability ``r``. Odd vs even weeks are half seasons, so factor 2."""
    return factor * r / (1 + (factor - 1) * r)


def fisher_ci(r: float, n: int, level: float = 0.95) -> tuple[float, float]:
    """Fisher-z confidence interval for a Pearson r over n pairs.

    Treats pairs as independent. Player-seasons of the same player are
    not, so these intervals are somewhat narrow; the paired deltas use a
    player-clustered bootstrap instead.
    """
    if n <= 3:
        return float("nan"), float("nan")
    half = norm.ppf(0.5 + level / 2) / np.sqrt(n - 3)
    z = np.arctanh(r)
    return float(np.tanh(z - half)), float(np.tanh(z + half))


def _identity(r: R) -> R:
    return r


def _transform(metric: str) -> Callable[[R], R]:
    return spearman_brown if metric == "reliability" else _identity


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < _MIN_PAIRS or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def _estimate(pairs: pd.DataFrame, metric: str, x: str = "x", y: str = "y") -> Estimate:
    f = _transform(metric)
    n = len(pairs)
    r = _pearson(pairs[x].to_numpy(float), pairs[y].to_numpy(float))
    if np.isnan(r):
        return Estimate(float("nan"), float("nan"), float("nan"), n)
    lo, hi = fisher_ci(r, n)
    return Estimate(f(r), f(lo), f(hi), n)


def _weighted_r(w: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Pearson r of (x, y) under each row of frequency weights ``w``
    (draws x rows): the r of each bootstrap resample, vectorized."""
    sw = w.sum(axis=1)
    mx, my = w @ x / sw, w @ y / sw
    cov = w @ (x * y) / sw - mx * my
    vx = w @ (x * x) / sw - mx * mx
    vy = w @ (y * y) / sw - my * my
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.asarray(cov / np.sqrt(vx * vy), dtype=float)


# ---------------------------------------------------------------------------
# Scoring a Formula over the panel
# ---------------------------------------------------------------------------


def melt_features(
    features: pd.DataFrame,
    specs: Mapping[str, tuple[str, str]],
    *,
    season: int,
    split: str,
) -> pd.DataFrame:
    """Turn a grader's wide features frame into long panel rows.

    ``specs`` maps component -> (raw value column, sample size column), as
    in each grader's ``_COMPONENT_SPECS``.
    """
    frames = [
        pd.DataFrame(
            {
                "player_id": features["player_id"].to_numpy(),
                "season": season,
                "split": split,
                "component": component,
                "raw": features[raw_col].astype(float).to_numpy(),
                "n": features[n_col].astype(float).to_numpy(),
            }
        )
        for component, (raw_col, n_col) in specs.items()
    ]
    return pd.concat(frames, ignore_index=True)


def score_panel(panel: pd.DataFrame, roster: pd.DataFrame, formula: Formula) -> pd.DataFrame:
    """Standardized Composite per Qualified (player_id, season, split).

    Within each season and split, as the graders do: shrink each
    Component toward its volume-weighted mean over every player in the
    panel, z-score it over the Qualified players, combine with the
    Formula (weights renormalized over the Components a player has), and
    divide by the Composite's SD over the Qualified players. A season-split
    with fewer than ``scoring.MIN_QUALIFIED_COHORT`` Qualified players is
    skipped, as production would not grade it.

    Returns columns player_id, season, split, composite.
    """
    missing_k = sorted(set(formula.weights) - set(formula.shrinkage_k))
    if missing_k:
        raise ValueError(f"no shrinkage k for {missing_k}")

    qualified = roster.set_index(_KEYS)["qualified"].astype(bool)
    out: list[pd.DataFrame] = []
    for (season, split), rows in panel.groupby(["season", "split"], sort=True):
        raw = rows.pivot(index="player_id", columns="component", values="raw")
        n = rows.pivot(index="player_id", columns="component", values="n")
        mask = pd.Series(
            qualified.reindex(pd.MultiIndex.from_arrays([raw.index, [season] * len(raw)]))
            .fillna(False)
            .to_numpy(dtype=bool),
            index=raw.index,
        )
        z = pd.DataFrame(index=raw.index)
        for component in formula.weights:
            if component in raw.columns:
                shrunk = empirical_bayes.shrink_series(
                    raw[component], n[component], k=formula.shrinkage_k[component]
                )
                z[component] = zscore.zscore(shrunk, qualified_mask=mask)
        composite = scoring.raw_composite(z, formula.weights)
        cohort = composite[mask & composite.notna()]
        # As scoring.score: too few Qualified players to set a scale.
        if len(cohort) < scoring.MIN_QUALIFIED_COHORT or cohort.std(ddof=1) == 0:
            continue
        out.append(
            pd.DataFrame(
                {
                    "player_id": cohort.index,
                    "season": season,
                    "split": split,
                    "composite": (cohort / cohort.std(ddof=1)).to_numpy(),
                }
            )
        )
    if not out:
        return pd.DataFrame(columns=["player_id", "season", "split", "composite"])
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------------------
# Metric pairs: one row per observation, x = Composite, y = target
# ---------------------------------------------------------------------------


def _split(scores: pd.DataFrame, split: str, seasons: range) -> pd.DataFrame:
    s = scores[(scores["split"] == split) & scores["season"].isin(seasons)]
    return s[[*_KEYS, "composite"]]


def reliability_pairs(scores: pd.DataFrame, seasons: range) -> pd.DataFrame:
    """Odd-week (x) vs even-week (y) Composite per player-season."""
    odd = _split(scores, "odd", seasons).rename(columns={"composite": "x"})
    even = _split(scores, "even", seasons).rename(columns={"composite": "y"})
    return odd.merge(even, on=_KEYS)


def yoy_pairs(scores: pd.DataFrame, roster: pd.DataFrame, seasons: range) -> pd.DataFrame:
    """Full-season Composite in N (x) vs N+1 (y), both seasons in
    ``seasons`` and Qualified. ``changer`` is True when the player's team
    differs between the two seasons, NA when either team is unknown."""
    full = _split(scores, "full", seasons)
    following = full.assign(season=full["season"] - 1).rename(columns={"composite": "y"})
    pairs = full.rename(columns={"composite": "x"}).merge(following, on=_KEYS)
    teams = roster.set_index(_KEYS)["team"]
    team = teams.reindex(pd.MultiIndex.from_frame(pairs[_KEYS])).to_numpy()
    team_next = teams.reindex(
        pd.MultiIndex.from_arrays([pairs["player_id"], pairs["season"] + 1])
    ).to_numpy()
    known = pd.notna(team) & pd.notna(team_next)
    pairs["changer"] = pd.array(np.where(known, team != team_next, False), dtype="boolean")
    pairs.loc[~known, "changer"] = pd.NA
    return pairs


def next_primary_pairs(
    scores: pd.DataFrame, panel: pd.DataFrame, primary: str, seasons: range
) -> pd.DataFrame:
    """Full-season Composite in N (x) vs the raw primary Component in N+1
    (y), for players Qualified in both seasons."""
    full = _split(scores, "full", seasons)
    prim = panel[
        (panel["split"] == "full") & (panel["component"] == primary) & panel["season"].isin(seasons)
    ][[*_KEYS, "raw"]]
    qualified_next = full[_KEYS].assign(season=full["season"] - 1)
    target = (
        prim.assign(season=prim["season"] - 1)
        .rename(columns={"raw": "y"})
        .merge(qualified_next, on=_KEYS)
    )
    return full.rename(columns={"composite": "x"}).merge(target, on=_KEYS).dropna(subset=["y"])


def pro_bowl_pairs(scores: pd.DataFrame, pro_bowl: pd.DataFrame, seasons: range) -> pd.DataFrame:
    """Full-season Composite (x) vs same-season Pro Bowl label (y)."""
    labels = pro_bowl[[*_KEYS, "pro_bowl"]].rename(columns={"pro_bowl": "y"})
    return (
        _split(scores, "full", seasons).rename(columns={"composite": "x"}).merge(labels, on=_KEYS)
    )


def _pair_sets(
    scores: pd.DataFrame,
    roster: pd.DataFrame,
    panel: pd.DataFrame,
    primary: str,
    pro_bowl: pd.DataFrame | None,
    seasons: range,
) -> dict[str, pd.DataFrame]:
    yoy = yoy_pairs(scores, roster, seasons)
    sets = {
        "reliability": reliability_pairs(scores, seasons),
        "portability": yoy[yoy["changer"].fillna(False).astype(bool)],
        "yoy": yoy,
        "yoy_stayers": yoy[(~yoy["changer"]).fillna(False).astype(bool)],
        "next_primary": next_primary_pairs(scores, panel, primary, seasons),
    }
    if pro_bowl is not None:
        sets["pro_bowl"] = pro_bowl_pairs(scores, pro_bowl, seasons)
    return {m: df[[*_KEYS, "x", "y"]] for m, df in sets.items()}


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate(
    panel: pd.DataFrame,
    roster: pd.DataFrame,
    current: Formula,
    *,
    proposed: Formula | None = None,
    primary: str,
    pro_bowl: pd.DataFrame | None = None,
    windows: Mapping[str, range] = WINDOWS,
    n_boot: int = 2000,
    seed: int = 0,
) -> list[WindowReport]:
    """Score ``current`` (and ``proposed``) in each window.

    ``primary`` names the Component used as the next-season target.
    ``pro_bowl`` (player_id, season, pro_bowl) adds the face-validity row;
    pass only seasons with an observable label.

    Paired deltas resample players (all of a player's rows together) with
    one set of draws per window shared by every metric, seeded so reruns
    match.
    """
    cur_scores = score_panel(panel, roster, current)
    new_scores = score_panel(panel, roster, proposed) if proposed is not None else None

    reports: list[WindowReport] = []
    for name, seasons in windows.items():
        cur_sets = _pair_sets(cur_scores, roster, panel, primary, pro_bowl, seasons)
        if new_scores is None:
            current_est = {m: _estimate(df, m) for m, df in cur_sets.items()}
            reports.append(WindowReport(name, seasons, current_est, None, None))
            continue

        new_sets = _pair_sets(new_scores, roster, panel, primary, pro_bowl, seasons)
        paired = {
            m: cur_sets[m].merge(new_sets[m], on=_KEYS, suffixes=("_c", "_n")) for m in cur_sets
        }
        players = pd.Index(
            pd.unique(np.concatenate([df["player_id"].to_numpy() for df in paired.values()]))
        )
        rng = np.random.default_rng(seed)
        counts = (
            rng.multinomial(len(players), np.full(len(players), 1 / len(players)), n_boot)
            if len(players)
            else np.zeros((n_boot, 0))
        )

        current_est, proposed_est, delta_est = {}, {}, {}
        for m, df in paired.items():
            current_est[m] = _estimate(df, m, "x_c", "y_c")
            proposed_est[m] = _estimate(df, m, "x_n", "y_n")
            delta_est[m] = _paired_delta(df, m, counts[:, players.get_indexer(df["player_id"])])
        reports.append(WindowReport(name, seasons, current_est, proposed_est, delta_est))
    return reports


def _paired_delta(df: pd.DataFrame, metric: str, weights: np.ndarray) -> Estimate:
    f = _transform(metric)
    cols = {c: df[c].to_numpy(float) for c in ("x_c", "y_c", "x_n", "y_n")}
    r_c = _pearson(cols["x_c"], cols["y_c"])
    r_n = _pearson(cols["x_n"], cols["y_n"])
    if np.isnan(r_c) or np.isnan(r_n):
        return Estimate(float("nan"), float("nan"), float("nan"), len(df))
    draws = f(_weighted_r(weights, cols["x_n"], cols["y_n"])) - f(
        _weighted_r(weights, cols["x_c"], cols["y_c"])
    )
    lo, hi = np.nanpercentile(draws, [2.5, 97.5])
    return Estimate(f(r_n) - f(r_c), float(lo), float(hi), len(df))


def ship_rule(holdout: WindowReport) -> ShipVerdict:
    """The quantitative half of the ship rule, on hold-out paired deltas.

    Passes when neither Reliability nor Portability falls beyond noise
    (delta CI entirely below zero) or is missing (too few pairs to
    estimate: the guard fails closed), and at least one of Reliability,
    Portability or next-season prediction rises with a CI excluding zero.
    A change must also pass skill-tree / face-validity review, which no
    number replaces.
    """
    if holdout.delta is None:
        raise ValueError("the ship rule needs a proposed Formula")
    reasons: list[str] = []
    unestimated = [
        m for m in GUARDED_METRICS if m not in holdout.delta or np.isnan(holdout.delta[m].value)
    ]
    regressions = [m for m in GUARDED_METRICS if m in holdout.delta and holdout.delta[m].hi < 0]
    improvements = [
        m for m in IMPROVEMENT_METRICS if m in holdout.delta and holdout.delta[m].lo > 0
    ]
    for m in unestimated:
        reasons.append(f"{METRIC_LABELS[m]} could not be estimated on the hold-out")
    for m in regressions:
        reasons.append(f"{METRIC_LABELS[m]} falls beyond noise: {_fmt_delta(holdout.delta[m])}")
    for m in improvements:
        reasons.append(f"{METRIC_LABELS[m]} improves: {_fmt_delta(holdout.delta[m])}")
    if not improvements:
        reasons.append("no metric improves with a CI excluding zero")
    passes = not unestimated and not regressions and bool(improvements)
    return ShipVerdict(passes=passes, reasons=tuple(reasons))


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _fmt(est: Estimate) -> str:
    if np.isnan(est.value):
        return f"{'n/a':>22}"
    return f"{est.value:+.3f} [{est.lo:+.3f}, {est.hi:+.3f}]"


def _fmt_delta(est: Estimate) -> str:
    if np.isnan(est.value):
        return "n/a"
    return f"{est.value:+.3f} [{est.lo:+.3f}, {est.hi:+.3f}]"


def format_report(reports: list[WindowReport]) -> str:
    lines: list[str] = []
    for rep in reports:
        lines.append("")
        lines.append(f"{rep.name.upper()} {rep.seasons.start}-{rep.seasons.stop - 1}")
        header = f"{'metric':<30} {'n':>5}  {'current':>22}"
        if rep.proposed is not None:
            header += f"  {'proposed':>22}  {'delta (paired bootstrap)':>24}"
        lines.append(header)
        lines.append("-" * len(header))
        for m, est in rep.current.items():
            line = f"{METRIC_LABELS[m]:<30} {est.n:>5}  {_fmt(est):>22}"
            if rep.proposed is not None and rep.delta is not None:
                line += f"  {_fmt(rep.proposed[m]):>22}  {_fmt_delta(rep.delta[m]):>24}"
            lines.append(line)
    return "\n".join(lines)


__all__ = [
    "GUARDED_METRICS",
    "IMPROVEMENT_METRICS",
    "METRIC_LABELS",
    "SPLITS",
    "WINDOWS",
    "Estimate",
    "Formula",
    "ShipVerdict",
    "WindowReport",
    "evaluate",
    "fisher_ci",
    "format_report",
    "melt_features",
    "next_primary_pairs",
    "pro_bowl_pairs",
    "reliability_pairs",
    "score_panel",
    "ship_rule",
    "spearman_brown",
    "yoy_pairs",
]
