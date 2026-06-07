"""Preloaded scores for well-known public dbt projects.

These are the projects dbt Lens compares your score against in the
"Compare to famous projects" panel. Scores are PLACEHOLDER values — real
numbers can be obtained by running ``dbt parse`` on each repo and feeding
its ``manifest.json`` back into :func:`dbtlens.scorer.score_project`.

TODO: Replace these placeholders with real scores. The procedure is:
    1. For each repo below, run ``dbt parse`` (or ``dbt build``) to
       generate ``target/manifest.json``.
    2. Use the same ``parse_manifest`` + ``score_project`` pipeline we
       ship to compute the real number.
    3. Drop it into ``FAMOUS_PROJECTS`` below.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class FamousProject:
    """A reference project used in the comparison panel."""

    key: str
    display_name: str
    repo_url: str
    score: int  # 0..100


# ---- Placeholder scores. Replace with real values when measured. ----
FAMOUS_PROJECTS: tuple[FamousProject, ...] = (
    FamousProject(
        key="jaffle_shop",
        display_name="jaffle_shop",
        repo_url="https://github.com/dbt-labs/jaffle_shop",
        score=78,
    ),
    FamousProject(
        key="dbt_utils",
        display_name="dbt-labs/dbt-utils",
        repo_url="https://github.com/dbt-labs/dbt-utils",
        score=85,
    ),
    FamousProject(
        key="jaffle_shop_duckdb",
        display_name="dbt-labs/jaffle_shop_duckdb",
        repo_url="https://github.com/dbt-labs/jaffle_shop_duckdb",
        score=72,
    ),
    FamousProject(
        key="dbt_date",
        display_name="calogica/dbt-date",
        repo_url="https://github.com/calogica/dbt-date",
        score=68,
    ),
    FamousProject(
        key="dbt_expectations",
        display_name="dbt-labs/dbt-expectations",
        repo_url="https://github.com/calogica/dbt-expectations",
        score=90,
    ),
)


def get_famous_projects() -> tuple[FamousProject, ...]:
    """Return the canonical list of famous projects."""
    return FAMOUS_PROJECTS


def rank_against(
    user_score: int,
    *,
    user_label: str = "Your project",
) -> list[tuple[str, int, bool]]:
    """Build the comparison dataset.

    Args:
        user_score: The user's 0..100 score.
        user_label: Display name for the user's bar.

    Returns:
        A list of (label, score, is_user) tuples, sorted descending by
        score. The user's bar is always present exactly once, marked with
        ``is_user=True``.
    """
    rows: list[tuple[str, int, bool]] = [
        (p.display_name, p.score, False) for p in FAMOUS_PROJECTS
    ]
    rows.append((user_label, user_score, True))
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


def user_rank(user_score: int) -> int:
    """Return the user's 1-based rank among 6 projects (user + 5 famous)."""
    rows = rank_against(user_score)
    for i, (_, _, is_user) in enumerate(rows, start=1):
        if is_user:
            return i
    return len(rows)


def maybe_load_from_json(path: str | Path) -> tuple[FamousProject, ...] | None:
    """Load an optional override list from ``data/famous_projects.json``.

    If the file does not exist or is malformed, returns ``None`` and the
    module-level :data:`FAMOUS_PROJECTS` is used instead.
    """
    p = Path(path)
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, list):
        return None
    out: list[FamousProject] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            out.append(
                FamousProject(
                    key=str(entry["key"]),
                    display_name=str(entry["display_name"]),
                    repo_url=str(entry.get("repo_url", "")),
                    score=int(entry["score"]),
                )
            )
        except (KeyError, ValueError):
            continue
    return tuple(out) or None


__all__ = [
    "FamousProject",
    "FAMOUS_PROJECTS",
    "get_famous_projects",
    "rank_against",
    "user_rank",
    "maybe_load_from_json",
]
