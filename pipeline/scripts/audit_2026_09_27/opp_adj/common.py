"""Shared machinery: pbp loading with production filters + ridge opponent ratings."""
from __future__ import annotations
import pathlib
import numpy as np
import pandas as pd

from nfl_grades.config import settings

REPO = pathlib.Path(__file__).resolve().parents[4]
PBP = settings.pipeline_cache_dir / "raw" / "pbp"
OUT = settings.pipeline_cache_dir / "audit_2026_09_27" / "opp_adj"
OUT.mkdir(parents=True, exist_ok=True)
SEASONS = list(range(2016, 2026))

COLS = ["season", "season_type", "week", "game_id", "play_id", "posteam", "defteam", "epa", "success",
        "qb_dropback", "cpoe", "passer_player_id", "receiver_player_id", "rusher_player_id",
        "aborted_play", "two_point_attempt", "qb_kneel", "qb_scramble", "rush_attempt", "pass_attempt",
        "complete_pass", "qtr", "score_differential", "game_seconds_remaining", "yards_gained",
        "interception", "pass_touchdown", "sack"]


def _b(s):
    return s.fillna(0).astype(float) == 1


def load_pbp(season: int) -> pd.DataFrame:
    d = pd.read_parquet(PBP / f"{season}.parquet", columns=COLS)
    d = d[(d.season_type == "REG") & d.epa.notna() & d.posteam.notna() & d.defteam.notna()].copy()
    garbage = ((d.qtr >= 4) & (d.score_differential.abs() > 21)) | (
        (d.qtr == 4) & (d.game_seconds_remaining < 300) & (d.score_differential.abs() > 14))
    base = ~garbage & ~_b(d.two_point_attempt)
    # QB set (QB_DROPBACK_FILTER_SQL): dropbacks w/ passer_player_id (scrambles excluded de facto)
    d["is_db"] = base & _b(d.qb_dropback) & ~_b(d.aborted_play) & d.passer_player_id.notna()
    d["is_cpoe"] = d.is_db & _b(d.pass_attempt) & d.cpoe.notna()
    # RB rush set
    d["is_rush"] = base & _b(d.rush_attempt) & d.rusher_player_id.notna() & ~_b(d.qb_kneel) & ~_b(d.qb_scramble)
    # receiver target set (RB_REC_FILTER_SQL)
    d["is_tgt"] = base & _b(d.pass_attempt) & d.receiver_player_id.notna()
    d["success"] = d.success.astype(float)
    return d


# play set name -> (flag col, value col)
SETS = {
    "db_epa": ("is_db", "epa"),
    "db_succ": ("is_db", "success"),
    "cpoe": ("is_cpoe", "cpoe"),
    "rush_epa": ("is_rush", "epa"),
    "rush_succ": ("is_rush", "success"),
    "tgt_epa": ("is_tgt", "epa"),
    "tgt_succ": ("is_tgt", "success"),
}


def cells(d: pd.DataFrame, flag: str, val: str) -> pd.DataFrame:
    x = d[d[flag]]
    return x.groupby(["posteam", "defteam"]).agg(s=(val, "sum"), n=(val, "size"), ss=(val, lambda v: (v**2).sum())).reset_index()


def ridge_ratings(c: pd.DataFrame, lam: float, teams: list[str], prior_def: pd.Series | None = None,
                  prior_off: pd.Series | None = None, exclude_off: str | None = None):
    """WLS ridge on cell means: y = mu + o[posteam] + d[defteam].
    Penalty lam*(o-o0)^2 + lam*(d-d0)^2. Returns (mu, off Series, def Series), def centered (play-weighted)."""
    if exclude_off is not None:
        c = c[c.posteam != exclude_off]
    T = len(teams); idx = {t: i for i, t in enumerate(teams)}
    n = c.n.to_numpy(float); s = c.s.to_numpy(float)
    oi = c.posteam.map(idx).to_numpy(); di = c.defteam.map(idx).to_numpy() + T
    mu = s.sum() / n.sum()
    r = s - n * mu  # sum of residuals per cell
    A = np.zeros((2 * T, 2 * T)); b = np.zeros(2 * T)
    np.add.at(A, (oi, oi), n); np.add.at(A, (di, di), n); np.add.at(A, (oi, di), n); np.add.at(A, (di, oi), n)
    np.add.at(b, oi, r); np.add.at(b, di, r)
    beta0 = np.zeros(2 * T)
    if prior_off is not None:
        beta0[:T] = prior_off.reindex(teams).fillna(0).to_numpy()
    if prior_def is not None:
        beta0[T:] = prior_def.reindex(teams).fillna(0).to_numpy()
    A += lam * np.eye(2 * T); b += lam * beta0
    beta = np.linalg.solve(A, b)
    off = pd.Series(beta[:T], index=teams); de = pd.Series(beta[T:], index=teams)
    # center defense on play-weighted mean so league-average schedule => 0 adjustment
    w = c.groupby("defteam").n.sum().reindex(teams).fillna(0)
    de = de - (de * w).sum() / w.sum()
    return mu, off, de


def estimate_lambda(all_cells: list[pd.DataFrame]) -> tuple[float, float, float]:
    """Method-of-moments: per-play variance sigma2 vs between-defense true variance tau2."""
    s2s, tau2s = [], []
    for c in all_cells:
        g = c.groupby("defteam").agg(s=("s", "sum"), n=("n", "sum"), ss=("ss", "sum"))
        m = g.s / g.n
        var_play = (g.ss / g.n - m**2)  # within-team per-play variance
        sigma2 = float((var_play * g.n).sum() / g.n.sum())
        obs_var = float(m.var(ddof=1))
        tau2 = obs_var - sigma2 * float((1 / g.n).mean())
        s2s.append(sigma2); tau2s.append(tau2)
    sigma2 = float(np.mean(s2s)); tau2 = max(float(np.mean(tau2s)), 1e-9)
    return sigma2 / tau2, sigma2, tau2


def loo_def_ratings(c: pd.DataFrame, lam: float, teams, prior_def=None, prior_off=None) -> pd.DataFrame:
    """Return DataFrame [offteam, defteam, d] = defense rating computed excluding offteam's own plays."""
    rows = []
    for T in teams:
        _, _, de = ridge_ratings(c, lam, teams, prior_def, prior_off, exclude_off=T)
        rows.append(pd.DataFrame({"posteam": T, "defteam": de.index, "d_loo": de.to_numpy()}))
    return pd.concat(rows, ignore_index=True)


def simple_loo_def(c: pd.DataFrame, lam: float, teams) -> pd.DataFrame:
    """Naive: defense mean allowed (excl. games vs offteam) minus league mean, shrunk n/(n+lam). No offense adj."""
    rows = []
    mu = c.s.sum() / c.n.sum()
    for T in teams:
        cc = c[c.posteam != T]
        g = cc.groupby("defteam").agg(s=("s", "sum"), n=("n", "sum")).reindex(teams).fillna(0)
        dev = (g.s / g.n.replace(0, np.nan) - mu).fillna(0) * g.n / (g.n + lam)
        rows.append(pd.DataFrame({"posteam": T, "defteam": teams, "d_loo": dev.to_numpy()}))
    return pd.concat(rows, ignore_index=True)
