#!/usr/bin/env python3
"""Compare eval results across versions.

Usage:
    python3 scripts/eval/compare.py \
        data/eval_results/eval_hybrid_20260228_182057.json \
        data/eval_results/eval_v2_hybrid.json
"""
import json
import sys
from pathlib import Path


METRIC_KEYS = [
    ("hit_rate@1",  "Hit@1",  "pct"),
    ("hit_rate@3",  "Hit@3",  "pct"),
    ("hit_rate@5",  "Hit@5",  "pct"),
    ("hit_rate@10", "Hit@10", "pct"),
    ("mrr",         "MRR",    "float"),
    ("failures",    "Failures", "int"),
    ("low_rank_count", "Low rank (>5)", "int"),
]


def load_eval(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def label_from_path(path: str) -> str:
    """Extract a short label from filename."""
    stem = Path(path).stem
    # eval_hybrid_20260228_182057 -> hybrid
    # eval_v2_hybrid -> v2_hybrid
    parts = stem.split("_")
    if parts[0] == "eval":
        parts = parts[1:]
    # Drop timestamp-like parts (all digits, 6+ chars)
    parts = [p for p in parts if not (p.isdigit() and len(p) >= 6)]
    return "_".join(parts) if parts else stem


def format_val(val, fmt: str) -> str:
    if fmt == "pct":
        return f"{val:.1%}"
    elif fmt == "float":
        return f"{val:.4f}"
    else:
        return str(int(val))


def format_delta(delta, fmt: str, lower_is_better: bool = False) -> str:
    if fmt == "pct":
        s = f"{delta:+.1%}"
    elif fmt == "float":
        s = f"{delta:+.4f}"
    else:
        s = f"{delta:+d}" if isinstance(delta, int) else f"{delta:+.0f}"

    # Color logic: green for improvement, red for regression
    improved = (delta < 0) if lower_is_better else (delta > 0)
    if delta == 0:
        return s
    return f"{s} {'▲' if improved else '▼'}"


def compare(paths: list[str]):
    evals = []
    for p in paths:
        data = load_eval(p)
        label = label_from_path(p)
        evals.append((label, data["metrics"]))

    # Column widths
    label_width = max(len(label) for label, _ in evals)
    col_width = max(14, label_width + 2)

    # Header
    metric_col = 16
    header = " " * metric_col
    for label, _ in evals:
        header += f"{label:>{col_width}}"
    if len(evals) >= 2:
        header += f"{'Δ':>{col_width}}"
    print(header)
    print("-" * len(header))

    # Rows
    for key, display_name, fmt in METRIC_KEYS:
        row = f"{display_name:<{metric_col}}"
        values = []
        for label, metrics in evals:
            val = metrics.get(key, 0)
            values.append(val)
            row += f"{format_val(val, fmt):>{col_width}}"

        # Delta between first and last
        if len(evals) >= 2:
            delta = values[-1] - values[0]
            lower_is_better = key in ("failures", "low_rank_count")
            row += f"{format_delta(delta, fmt, lower_is_better):>{col_width}}"

        print(row)

    # Failure detail comparison
    if len(evals) >= 2:
        print(f"\n{'='*60}")
        print("Failure analysis (last vs first):")
        first_data = load_eval(paths[0])
        last_data = load_eval(paths[-1])

        first_fails = {d["question"] for d in first_data["details"]
                       if not d["found"]}
        last_fails = {d["question"] for d in last_data["details"]
                      if not d["found"]}

        fixed = first_fails - last_fails
        regressed = last_fails - first_fails

        if fixed:
            print(f"\n  Fixed ({len(fixed)}):")
            for q in sorted(fixed):
                print(f"    + {q[:70]}")

        if regressed:
            print(f"\n  Regressed ({len(regressed)}):")
            for q in sorted(regressed):
                print(f"    - {q[:70]}")

        if not fixed and not regressed:
            if first_fails == last_fails:
                print(f"  Same {len(first_fails)} failures in both.")
            else:
                print("  No changes in failures.")


def main():
    if len(sys.argv) < 3:
        print("Usage: compare.py <eval1.json> <eval2.json> [eval3.json ...]")
        print("  Compare retrieval metrics across eval result files.")
        sys.exit(1)

    paths = sys.argv[1:]
    for p in paths:
        if not Path(p).exists():
            print(f"Error: File not found: {p}", file=sys.stderr)
            sys.exit(1)

    compare(paths)


if __name__ == "__main__":
    main()
