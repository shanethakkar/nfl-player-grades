"""Codegen `web/src/lib/grades.ts` weight dicts from `weights.py`.

Single source of truth for component weights is `pipeline/grading/weights.py`.
The web app needs the same values so the methodology page and `componentWeight()`
return correct numbers. This script keeps the two in sync.

Usage:
    python pipeline/scripts/sync_weights_to_web.py        # write
    python pipeline/scripts/sync_weights_to_web.py --check # exit 1 if drift

Looks for AUTOGEN-BEGIN / AUTOGEN-END markers in grades.ts and rewrites only
that block. Hand-edited sections (component formats, role labels, helper
functions) are untouched.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GRADES_TS = REPO_ROOT / "web" / "src" / "lib" / "grades.ts"

BEGIN_MARKER = "// AUTOGEN-BEGIN weights"
END_MARKER = "// AUTOGEN-END weights"


def _format_value(v: float) -> str:
    """Emit the value with minimum precision that round-trips to ``v``.

    Examples: 0.5 -> "0.50", 0.406 -> "0.406", -0.05 -> "-0.05".

    We use a clamped 2-3-4 decimal ladder rather than ``repr(v)`` so the
    generated file is stable across Python versions and reads cleanly.
    """
    for digits in (2, 3, 4):
        s = f"{v:.{digits}f}"
        if abs(float(s) - v) < 1e-12:
            return s
    return f"{v:.6f}"


def _emit_dict_lines(name: str, weights: dict[str, float]) -> list[str]:
    if not weights:
        return [f"const {name}: Record<string, number> = {{}};"]
    key_width = max(len(f"{k}:") for k in weights) + 1
    # Right-align the value within a fixed value column so negatives line up
    # cleanly with positives.
    formatted_values = [_format_value(v) for v in weights.values()]
    val_width = max(len(s) for s in formatted_values)
    lines = [f"const {name}: Record<string, number> = {{"]
    for (k, v), s in zip(weights.items(), formatted_values, strict=True):
        key_part = f"{k}:".ljust(key_width)
        val_part = s.rjust(val_width)
        lines.append(f"  {key_part} {val_part},")
    lines.append("};")
    return lines


def _render_block(component_weights: dict[str, float], te_blocking: dict[str, float]) -> str:
    lines: list[str] = [BEGIN_MARKER]
    lines.extend(_emit_dict_lines("COMPONENT_WEIGHTS", component_weights))
    lines.append("")
    lines.extend(_emit_dict_lines("TE_BLOCKING_WEIGHTS", te_blocking))
    lines.append(END_MARKER)
    return "\n".join(lines)


def _load_weights():
    """Import weight dicts from pipeline/grading/weights.py."""
    # Make pipeline/src importable without installing the package.
    src_dir = REPO_ROOT / "pipeline" / "src"
    sys.path.insert(0, str(src_dir))
    try:
        from nfl_grades.grading.weights import (  # noqa: PLC0415
            CB_V1_WEIGHTS,
            EDGE_V1_WEIGHTS,
            IDL_V1_WEIGHTS,
            K_V1_WEIGHTS,
            LB_V1_WEIGHTS,
            P_V1_WEIGHTS,
            QB_V1_WEIGHTS,
            RB_V1_WEIGHTS,
            S_V1_WEIGHTS,
            TE_V1_BLOCKING_WEIGHTS,
            TE_V1_WEIGHTS,
            WR_V1_WEIGHTS,
        )
    finally:
        sys.path.pop(0)

    # Preserve the per-position grouping in the emitted dict for readability,
    # even though TypeScript doesn't care about insertion order semantically.
    flat: dict[str, float] = {}
    for d in (
        QB_V1_WEIGHTS, RB_V1_WEIGHTS, WR_V1_WEIGHTS, TE_V1_WEIGHTS,
        CB_V1_WEIGHTS, S_V1_WEIGHTS, EDGE_V1_WEIGHTS, IDL_V1_WEIGHTS,
        LB_V1_WEIGHTS, K_V1_WEIGHTS, P_V1_WEIGHTS,
    ):
        flat.update(d)
    return flat, dict(TE_V1_BLOCKING_WEIGHTS)


def _splice(text: str, new_block: str) -> str:
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(
            f"missing AUTOGEN markers in {GRADES_TS}; expected\n"
            f"  {BEGIN_MARKER}\n  ...\n  {END_MARKER}\n"
            "Add them around the COMPONENT_WEIGHTS + TE_BLOCKING_WEIGHTS dicts."
        )
    end_line_end = text.find("\n", end)
    if end_line_end == -1:
        end_line_end = len(text)
    return text[:start] + new_block + text[end_line_end:]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="Exit 1 if grades.ts is out of sync (CI mode).")
    args = ap.parse_args()

    main_weights, blocking = _load_weights()
    new_block = _render_block(main_weights, blocking)
    current = GRADES_TS.read_text(encoding="utf-8")
    new_text = _splice(current, new_block)

    if args.check:
        if current.replace("\r\n", "\n") != new_text.replace("\r\n", "\n"):
            print(f"DRIFT: {GRADES_TS} is out of sync with weights.py.")
            print("Run `python pipeline/scripts/sync_weights_to_web.py` to fix.")
            return 1
        print(f"OK: {GRADES_TS} matches weights.py.")
        return 0

    if current == new_text:
        print(f"no change ({GRADES_TS})")
        return 0
    GRADES_TS.write_text(new_text, encoding="utf-8")
    print(f"updated {GRADES_TS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
