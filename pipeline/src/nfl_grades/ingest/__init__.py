"""Ingestion: pull raw data from nflreadpy, cache as parquet, load into Postgres.

Architecture (see ADRs 0009 and 0010):

    nflreadpy.load_*(...)          (polars DataFrame, network call)
        |
        v
    _cache.cache_or_fetch(...)     (parquet on disk + manifest, .to_pandas())
        |
        v
    ingest/<source>.py             (transform pandas -> typed rows, FK lookups)
        |
        v
    Postgres typed tables          (players, player_seasons, ...)

One module per data source. Each module exposes a `run(season: int)` function
that is idempotent (safe to re-run) and writes a row to `pipeline_runs`.

Only `_cache.py` is allowed to import `nflreadpy`. Concrete ingesters call
`cache_or_fetch(source, season)` and receive a pandas DataFrame.

Modules (to be implemented in build step 1):
    _cache         - parquet cache + manifest, the only nflreadpy importer
    rosters        - team rosters     (nflreadpy.load_rosters)
    pbp            - play-by-play     (nflreadpy.load_pbp)
    ngs            - Next Gen Stats   (nflreadpy.load_nextgen_stats)
    depth_charts   - depth charts     (nflreadpy.load_depth_charts)
    snap_counts    - snap counts      (nflreadpy.load_snap_counts)
    ftn            - FTN charting     (nflreadpy.load_ftn_charting)
"""
