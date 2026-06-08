"""CLI entrypoint for dbt-lens.

Usage:
    python -m dbtlens manifest.json
    python -m dbtlens https://github.com/owner/repo/raw/main/target/manifest.json
    python -m dbtlens --json manifest.json
    python -m dbtlens --card manifest.json output_card.png
    python -m dbtlens --dag manifest.json output_dag.html

Run ``dbt parse`` (or ``dbt build``) first to generate ``target/manifest.json``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .parser import parse_manifest_file, parse_manifest_url, ProjectSnapshot
from .scorer import score_project, HealthScore
from .card_generator import generate_card, save_card


def _load_snapshot(src: str) -> ProjectSnapshot:
    """Load a ProjectSnapshot from a file path or URL."""
    if src.startswith("http://") or src.startswith("https://"):
        return parse_manifest_url(src)
    return parse_manifest_file(Path(src))


def _print_score(score: HealthScore, verbose: bool = False) -> None:
    """Print the health score to stdout."""
    print(f"\n{'='*50}")
    print(f"  {score.project_name}")
    print(f"{'='*50}")
    print(f"  Score:  {score.total}/100  ({score.grade})")
    print(f"  Models: {score.model_count}  |  Sources: {score.source_count}")
    print(f"  Tests:  {score.test_count}  |  Exposures: {score.exposure_count}")
    print(f"  Verdict: {score.verdict}")
    print()

    if verbose:
        print(f"  {'Dimension':<25} {'Earned':>8} {'Max':>6} {'%':>6}")
        print(f"  {'-'*25} {'-'*8} {'-'*6} {'-'*6}")
        for dim in score.dimensions:
            print(
                f"  {dim.name:<25} {dim.earned:>8.1f} {dim.possible:>6.1f} "
                f"{dim.percent:>6.1f}%"
            )
        print()
        if score.fixes:
            print(f"  Top {len(score.fixes)} fixes to recover points:")
            for fix in score.fixes:
                print(f"    {fix.rank}. [{fix.dimension}] {fix.title}")
                print(f"       +{fix.points_recoverable:.1f} pts recoverable")
                if fix.affected_models:
                    models = ", ".join(fix.affected_models[:3])
                    if len(fix.affected_models) > 3:
                        models += f" (+{len(fix.affected_models) - 3} more)"
                    print(f"       Models: {models}")
            print()


def _save_card(score: HealthScore, output_path: str) -> None:
    """Save a share card PNG for the score."""
    path = Path(output_path)
    img = generate_card(
        score.project_name,
        score.total,
        grade=score.grade,
    )
    save_card(img, str(path))
    print(f"Card saved to {path.resolve()}")


def _save_dag(snapshot: ProjectSnapshot, output_path: str) -> None:
    """Save a self-contained DAG HTML for the project."""
    from .dag_renderer import build_dag, render_with_vis_html

    nodes, edges = build_dag(snapshot)
    html = render_with_vis_html(nodes, edges)

    path = Path(output_path)
    path.write_text(html, encoding="utf-8")
    print(f"DAG saved to {path.resolve()} ({len(nodes)} nodes, {len(edges)} edges)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dbt-lens",
        description="Score your dbt project's health (0-100) across 6 dimensions.",
    )
    parser.add_argument(
        "source",
        help="Path to manifest.json, or a https:// URL pointing at one.",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output machine-readable JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--card", metavar="OUTPUT.png",
        help="Generate and save a 1200x630 share card PNG.",
    )
    parser.add_argument(
        "--dag", metavar="OUTPUT.html",
        help="Generate and save an interactive DAG HTML.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Show per-dimension breakdown and top fix suggestions.",
    )
    parser.add_argument(
        "--version", action="version", version="dbt-lens 1.0",
    )

    args = parser.parse_args(argv)

    try:
        snapshot = _load_snapshot(args.source)
    except FileNotFoundError:
        print(f"ERROR: File not found: {args.source}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: Failed to load manifest: {exc}", file=sys.stderr)
        return 1

    try:
        score = score_project(snapshot)
    except Exception as exc:
        print(f"ERROR: Failed to score project: {exc}", file=sys.stderr)
        return 1

    if args.json:
        import json
        output = {
            "project_name": score.project_name,
            "total": score.total,
            "grade": score.grade,
            "verdict": score.verdict,
            "model_count": score.model_count,
            "source_count": score.source_count,
            "test_count": score.test_count,
            "exposure_count": score.exposure_count,
            "dimensions": [
                {
                    "name": d.name,
                    "earned": round(d.earned, 2),
                    "possible": d.possible,
                    "percent": d.percent,
                    "missing": d.missing,
                    "notes": d.notes,
                }
                for d in score.dimensions
            ],
            "fixes": [
                {
                    "rank": f.rank,
                    "dimension": f.dimension,
                    "title": f.title,
                    "points_recoverable": round(f.points_recoverable, 1),
                    "affected_models": list(f.affected_models),
                }
                for f in score.fixes
            ],
        }
        print(json.dumps(output, indent=2))
        return 0

    _print_score(score, verbose=args.verbose)

    if args.card:
        try:
            _save_card(score, args.card)
        except Exception as exc:
            print(f"ERROR: Failed to save card: {exc}", file=sys.stderr)
            return 1

    if args.dag:
        try:
            _save_dag(snapshot, args.dag)
        except Exception as exc:
            print(f"ERROR: Failed to save DAG: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())