# tests/

Mirrors the package layout under `src/nfl_grades/`:

```
tests/
├── conftest.py
├── test_config.py              # top-level modules tested at the root
├── grading/
│   ├── test_sigmoid.py
│   ├── test_empirical_bayes.py
│   └── test_composite.py
├── ingest/
│   └── test_pbp.py
├── components/
└── career/
```

Each subpackage gets an `__init__.py` so pytest picks them up cleanly. Keep
test names matching the source: `src/nfl_grades/grading/sigmoid.py` ->
`tests/grading/test_sigmoid.py`.
