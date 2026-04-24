"""Stat components: raw data -> per-position component values.

Each module computes the components that feed a position's composite grade.
Output is written to the `stat_components` table.

Tier 1 (rich data):
    qb             - EPA/dropback, CPOE, sack rate, turnover-worthy plays, etc.
    rb             - EPA/rush, success rate, yards over expected (NGS), receiving
    wr_te          - YPRR, target share, aDOT, separation (NGS), YAC over expected

Tier 2 (decent data):
    cb             - targets, completion % allowed, yards per coverage snap, PBUs
    safety         - coverage + run-defense proxies
    edge           - pressures, pass-rush win rate, run-stop rate

Tier 3 (proxy stats, flagged in UI):
    ol             - pressure rate allowed, PFR sack/hit attribution
    idl            - pressures, run-stop rate
    lb             - tackles, missed-tackle rate, coverage snaps
    st             - kick/punt/return efficiency
"""
