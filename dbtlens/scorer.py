"""Compute a 0-100 health score for a dbt project.

The score is a weighted sum of six dimensions:

    +---------------------------+-------+
    | Test coverage             |   35  |
    | Documentation             |   20  |
    | Structure                 |   20  |
    | Naming                    |   10  |
    | Exposures                 |   10  |
    | Materialization maturity  |    5  |
    +---------------------------+-------+
    | Total                     |  100  |
    +---------------------------+-------+

Each dimension is described in detail in the docstring of the function that
computes it. The score is deterministic: same ``ProjectSnapshot`` in → same
:class:`HealthScore` out, every time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parser import ProjectSnapshot


# ---------------------------------------------------------------------------
# Constants — adjust carefully, the total MUST equal 100
# ---------------------------------------------------------------------------

# Dimension weights
W_TEST_COVERAGE = 35
W_DOCUMENTATION = 20
W_STRUCTURE = 20
W_NAMING = 10
W_EXPOSURES = 10
W_MATURITY = 5
TOTAL_WEIGHT = (
    W_TEST_COVERAGE
    + W_DOCUMENTATION
    + W_STRUCTURE
    + W_NAMING
    + W_EXPOSURES
    + W_MATURITY
)
assert TOTAL_WEIGHT == 100, "Dimension weights must sum to 100"

# Layer weight multipliers for test coverage scoring
LAYER_WEIGHT = {"marts": 2.0, "staging": 1.0, "intermediate": 0.5, "other": 1.0}

# Reasonable thresholds
MAX_HEALTHY_LINEAGE_DEPTH = 5
MAX_FINE = 100.0


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DimensionScore:
    """One dimension of the overall health score."""

    name: str
    earned: float
    possible: float
    notes: list[str] = field(default_factory=list)

    @property
    def percent(self) -> float:
        if self.possible <= 0:
            return 0.0
        return round(100.0 * self.earned / self.possible, 1)

    @property
    def missing(self) -> float:
        return max(0.0, round(self.possible - self.earned, 2))


@dataclass(frozen=True)
class FixSuggestion:
    """A single "top fix" item shown on the dashboard."""

    rank: int
    dimension: str
    title: str
    explanation: str
    points_recoverable: float
    # New: specific models that need attention (empty if N/A)
    affected_models: tuple[str, ...] = field(default_factory=tuple)
    # New: exact code / YAML snippets to copy-paste (title + code pairs)
    code_blocks: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HealthScore:
    """The final, fully-explained health score for a project."""

    total: int  # 0..100, rounded
    dimensions: tuple[DimensionScore, ...]
    fixes: tuple[FixSuggestion, ...]
    project_name: str
    model_count: int
    source_count: int
    test_count: int
    exposure_count: int

    @property
    def grade(self) -> str:
        """Letter grade, A+ through F."""
        if self.total >= 90:
            return "A+"
        if self.total >= 80:
            return "A"
        if self.total >= 70:
            return "B"
        if self.total >= 60:
            return "C"
        if self.total >= 50:
            return "D"
        return "F"

    @property
    def verdict(self) -> str:
        """A one-line summary the user sees next to the score."""
        if self.total >= 90:
            return "Battle-tested dbt project. Ship it."
        if self.total >= 75:
            return "Healthy project. A few polish items."
        if self.total >= 60:
            return "Decent foundation. Real gaps to close."
        if self.total >= 40:
            return "Risky. Production data is exposed."
        return "Critical. Do not trust the numbers yet."


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------


def _score_test_coverage(snapshot: ProjectSnapshot) -> DimensionScore:
    """Score test coverage (35 pts).

    Rules:
    - For each model, compute a weight based on its layer:
      marts=2.0, staging=1.0, intermediate=0.5, other=1.0.
    - A model is "covered" if it has at least one test referencing it
      (either model-level or column-level).
    - Score = (sum_of_covered_weights / sum_of_all_weights) * 35.
    - Penalty: every ``incremental`` model with zero tests costs 2 extra
      points each (capped at the dimension max).
    """
    models = [m for m in snapshot.models if m.is_model]
    if not models:
        return DimensionScore(
            name="Test coverage",
            earned=0.0,
            possible=W_TEST_COVERAGE,
            notes=["No models found in manifest."],
        )

    tested_ids = {t.attached_node for t in snapshot.tests}
    total_w = 0.0
    covered_w = 0.0
    untested_incremental: list[str] = []
    for m in models:
        w = LAYER_WEIGHT.get(m.layer, 1.0)
        total_w += w
        if m.unique_id in tested_ids:
            covered_w += w
        else:
            if m.materialized == "incremental":
                untested_incremental.append(m.name)

    base = (covered_w / total_w) * W_TEST_COVERAGE
    penalty = min(2.0 * len(untested_incremental), W_TEST_COVERAGE)
    earned = max(0.0, base - penalty)

    notes: list[str] = []
    if untested_incremental:
        notes.append(
            f"Incremental models without tests: {', '.join(untested_incremental[:5])}"
        )
    notes.append(
        f"Covered {covered_w:.1f} of {total_w:.1f} weighted models."
    )
    return DimensionScore(
        name="Test coverage",
        earned=earned,
        possible=W_TEST_COVERAGE,
        notes=notes,
    )


def _score_documentation(snapshot: ProjectSnapshot) -> DimensionScore:
    """Score documentation (20 pts).

    Rules:
    - A "documentation unit" is one (model + its columns) OR one (source + its
      columns). A unit is "fully documented" if it has a description AND every
      column has a description.
    - Base score = (documented_units / total_units) * 15.
    - Bonus: +5 if every source has a description (not column-level).
    """
    units: list[tuple[bool, bool]] = []  # (has_model_desc, has_all_col_desc)
    for m in snapshot.models:
        if not m.is_model:
            continue
        if not m.columns:
            # No columns — count as documented if description present.
            units.append((m.has_description, True))
            continue
        all_cols = all(c.description.strip() for c in m.columns)
        units.append((m.has_description, all_cols))

    for s in snapshot.sources:
        if not s.columns:
            units.append((s.has_description, True))
            continue
        all_cols = all(c.description.strip() for c in s.columns)
        units.append((s.has_description, all_cols))

    if not units:
        return DimensionScore(
            name="Documentation",
            earned=0.0,
            possible=W_DOCUMENTATION,
            notes=["No models or sources to document."],
        )

    fully = sum(1 for has_desc, has_cols in units if has_desc and has_cols)
    base = (fully / len(units)) * 15.0
    source_bonus = 5.0 if snapshot.sources and all(
        s.has_description for s in snapshot.sources
    ) else 0.0
    earned = min(W_DOCUMENTATION, base + source_bonus)

    notes = [f"Documented {fully} of {len(units)} model/source units."]
    if source_bonus == 0 and snapshot.sources:
        notes.append("Sources not fully described — missing the 5pt bonus.")
    return DimensionScore(
        name="Documentation",
        earned=earned,
        possible=W_DOCUMENTATION,
        notes=notes,
    )


def _score_structure(snapshot: ProjectSnapshot) -> DimensionScore:
    """Score DAG structure (20 pts).

    Rules (each contributes a slice of the 20):
    - No cycles:        +5
    - No orphan models: +5
    - Depth <= 5:       +5
    - All staging models named stg_*:  +2.5
    - All marts are in marts/ or named dim_/fct_:  +2.5
    """
    notes: list[str] = []
    earned = 0.0

    # No cycles
    if not snapshot.has_cycles:
        earned += 5.0
    else:
        notes.append("Cycle detected in model dependency graph.")

    # No orphans
    orphans = snapshot.orphans()
    if not orphans:
        earned += 5.0
    else:
        notes.append(f"{len(orphans)} orphan model(s): {', '.join(orphans[:3])}")

    # Lineage depth
    depth = snapshot.max_lineage_depth()
    if depth <= MAX_HEALTHY_LINEAGE_DEPTH:
        earned += 5.0
    else:
        notes.append(
            f"Lineage is {depth} levels deep — consider refactoring the long chain."
        )

    # Staging naming convention
    staging = [m for m in snapshot.models if m.layer == "staging"]
    if staging:
        bad_stg = [m.name for m in staging if not m.name.lower().startswith("stg_")]
        if not bad_stg:
            earned += 2.5
        else:
            notes.append(f"Staging models not prefixed stg_*: {', '.join(bad_stg[:3])}")
    else:
        # No staging layer is fine — don't penalize.
        earned += 2.5

    # Marts naming convention
    marts = [m for m in snapshot.models if m.layer == "marts"]
    if marts:
        bad_marts = [
            m.name
            for m in marts
            if not (
                m.name.lower().startswith(("fct_", "dim_"))
                or "/marts/" in m.file_path.lower().replace("\\", "/")
            )
        ]
        if not bad_marts:
            earned += 2.5
        else:
            notes.append(
                f"Mart models not in marts/ and not fct_/dim_: {', '.join(bad_marts[:3])}"
            )
    else:
        earned += 2.5

    return DimensionScore(
        name="Structure",
        earned=earned,
        possible=W_STRUCTURE,
        notes=notes,
    )


_SNAKE_OK = re.compile(r"^[a-z][a-z0-9_]*$")


def _score_naming(snapshot: ProjectSnapshot) -> DimensionScore:
    """Score naming consistency (10 pts).

    Rules:
    - A model name is "good" if it's all lowercase snake_case (starts with
      a letter, only [a-z0-9_]).
    - Score = (good / total) * 10.
    """
    models = [m for m in snapshot.models if m.is_model]
    if not models:
        return DimensionScore(
            name="Naming",
            earned=0.0,
            possible=W_NAMING,
            notes=["No models to evaluate."],
        )
    good = sum(1 for m in models if _SNAKE_OK.match(m.name))
    earned = (good / len(models)) * W_NAMING
    bad = [m.name for m in models if not _SNAKE_OK.match(m.name)]
    notes: list[str] = []
    if bad:
        notes.append(f"Non-snake_case model names: {', '.join(bad[:5])}")
    return DimensionScore(
        name="Naming",
        earned=earned,
        possible=W_NAMING,
        notes=notes,
    )


def _score_exposures(snapshot: ProjectSnapshot) -> DimensionScore:
    """Score exposure coverage (10 pts).

    Rules:
    - +2 per exposure, up to 10.
    - If no exposures at all, 0.
    - Exposures signal that the project knows who consumes its data — a
      sign of operational maturity.
    """
    n = len(snapshot.exposures)
    earned = min(W_EXPOSURES, 2.0 * n)
    notes: list[str] = []
    if n == 0:
        notes.append("No exposures defined. Add a `exposures:` block to your project.")
    else:
        notes.append(f"{n} exposure(s) defined.")
    return DimensionScore(
        name="Exposures",
        earned=earned,
        possible=W_EXPOSURES,
        notes=notes,
    )


def _score_materialization_maturity(snapshot: ProjectSnapshot) -> DimensionScore:
    """Score materialization maturity (5 pts).

    Rules:
    - +1 if any model uses incremental, snapshot, or ephemeral.
    - +1 if at least 3 of {view, table, incremental, snapshot, ephemeral}
      are used.
    - +2 if all "incremental-eligible" models (heuristic: fct_/dim_ mart with
      >5 parents) are actually incremental.
    """
    models = [m for m in snapshot.models if m.is_model]
    mats = {m.materialized for m in models}
    earned = 0.0
    notes: list[str] = []

    if mats & {"incremental", "snapshot", "ephemeral"}:
        earned += 1.0
    else:
        notes.append("No incremental/snapshot/ephemeral models yet.")

    diverse = mats & {"view", "table", "incremental", "snapshot", "ephemeral"}
    if len(diverse) >= 3:
        earned += 1.0
    else:
        notes.append(f"Only {len(diverse)} materialization types in use.")

    # Right-tool-for-the-job check
    mart_ids = {m.unique_id for m in snapshot.models if m.is_model and m.layer == "marts"}
    id_to_parents: dict[str, int] = {m.unique_id: len(m.depends_on) for m in models}
    eligible = [
        m
        for m in models
        if m.unique_id in mart_ids
        and (m.name.lower().startswith(("fct_", "dim_")))
        and id_to_parents[m.unique_id] >= 2
    ]
    if eligible:
        not_inc = [m for m in eligible if m.materialized != "incremental"]
        if not not_inc:
            earned += 2.0
        else:
            notes.append(
                f"Mart models that look incremental-eligible but aren't: "
                f"{', '.join(m.name for m in not_inc[:3])}"
            )
    else:
        # No eligible marts — award the 2 points so we don't punish small projects.
        earned += 2.0

    return DimensionScore(
        name="Materialization maturity",
        earned=earned,
        possible=W_MATURITY,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Top fixes
# ---------------------------------------------------------------------------


def _generate_fixes(
    dimensions: tuple[DimensionScore, ...],
    snapshot: ProjectSnapshot,
) -> tuple[FixSuggestion, ...]:
    """Pick the top 3 fixes based on which dimensions lost the most points.
    
    Each fix includes specific model names and copy-paste-ready code snippets.
    """
    candidates: list[FixSuggestion] = []

    tested_ids = {t.attached_node for t in snapshot.tests}

    for d in dimensions:
        if d.missing <= 0:
            continue

        if d.name == "Test coverage":
            # Find untested models, prioritise marts
            untested_marts = [
                m.name for m in snapshot.models
                if m.is_model and m.layer == "marts"
                and m.unique_id not in tested_ids
            ]
            untested_other = [
                m.name for m in snapshot.models
                if m.is_model and m.layer != "marts"
                and m.unique_id not in tested_ids
            ]
            all_names = untested_marts + untested_other
            top_names = all_names[:5]

            # Build code snippet
            if top_names:
                example_model = top_names[0]
                snippet = f"""\
# Add to your model's .yml file (e.g. models/marts/{example_model}.yml)

version: 2

models:
  - name: {example_model}
    description: "One-sentence description of what this model does and why it exists."
    tests:
      - not_null:
          column_name: id          # ← replace with actual primary key
      - unique:
          column_name: id          # ← replace with actual primary key
    columns:
      - name: id
        description: "Primary key — guaranteed unique and non-null."
      - name: created_at
        description: "Timestamp when the record was created."
      - name: updated_at
        description: "Timestamp when the record was last modified." """
            else:
                snippet = ""

            candidates.append(
                FixSuggestion(
                    rank=0,
                    dimension=d.name,
                    title="Add tests to your most important models",
                    explanation=(
                        "Marts (fct_/dim_) are weighted 2× — adding tests "
                        "there recovers the most points. Start with your "
                        "fact and dimension tables, then work outward to "
                        "staging and intermediate layers."
                    ),
                    points_recoverable=d.missing,
                    affected_models=tuple(top_names),
                    code_blocks=(
                        ("YAML — add to models/<layer>/<model>.yml", snippet),
                    ) if snippet else (),
                )
            )

        elif d.name == "Documentation":
            # Find undocumented or partially-documented models
            undocumented = [
                m.name for m in snapshot.models
                if m.is_model and not m.has_description
            ]
            partially_doc = [
                m.name for m in snapshot.models
                if m.is_model and m.has_description
                and m.columns
                and any(not c.description.strip() for c in m.columns)
            ]
            top_names = (undocumented + partially_doc)[:5]

            snippet = ""
            if top_names:
                ex = top_names[0]
                snippet = f"""\
# Option 1: In the .yml file (recommended)
version: 2

models:
  - name: {ex}
    description: "Describe what this model does and what business question it answers."

# Option 2: In the .sql model file itself
{{{{ config(materialized='table') }}}}

{{{{ doc '{ex}_description' }}}}

SELECT ...

# Then in dbt_project.yml / models/*.yml define the doc block:
# docs:
#   - name: {ex}_description
#     description: |
#       Full description of what this model does.
#       Can span multiple lines."""

            candidates.append(
                FixSuggestion(
                    rank=0,
                    dimension=d.name,
                    title="Document your models and columns",
                    explanation=(
                        "Every model needs a `description:` and every column "
                        "needs a one-line description. Undocumented models "
                        "are a maintenance nightmare — six months later, "
                        "nobody knows what `int_pivot_3` actually does."
                    ),
                    points_recoverable=d.missing,
                    affected_models=tuple(top_names),
                    code_blocks=(
                        ("YAML + SQL — two ways to add descriptions", snippet),
                    ) if snippet else (),
                )
            )

        elif d.name == "Structure":
            orphans = snapshot.orphans()
            depth = snapshot.max_lineage_depth()
            issues: list[str] = []
            if orphans:
                issues += orphans[:3]
            if depth > MAX_HEALTHY_LINEAGE_DEPTH:
                issues.append(f"Lineage is {depth} levels deep (max recommended: 5)")

            snippet = ""
            if orphans:
                example = orphans[0]
                snippet = f"""\
# Orphan model: {example}

# Check if {example} is actually used anywhere:
grep -r "{example}" models/

# If not used → either delete it or document why it exists.
# If used but not wired in dbt's dependency graph,
# make sure it's referenced via ref() in a downstream model.

# Common cause of orphans: the model file exists but isn't
# included via a ref() call anywhere in the project."""

            candidates.append(
                FixSuggestion(
                    rank=0,
                    dimension=d.name,
                    title="Clean up your DAG structure",
                    explanation=(
                        "Orphan models (no parents and no children) are dead "
                        "code — they run but nobody uses them. Lineage deeper "
                        "than 5 levels is hard to debug. Keep the DAG flat and "
                        "linear: staging → intermediate → marts."
                    ),
                    points_recoverable=d.missing,
                    affected_models=tuple(issues[:5]),
                    code_blocks=(
                        ("Bash — find orphan usage", snippet),
                    ) if snippet else (),
                )
            )

        elif d.name == "Naming":
            bad = [
                m.name for m in snapshot.models
                if m.is_model and not _SNAKE_OK.match(m.name)
            ]
            if bad:
                example = bad[0]
                snippet = f"""\
# Rename model file and update all ref() calls

# 1. Rename the file:
mv models/{example}.sql models/{example.lower().replace('_', '-')}.sql

# 2. Find and update all ref() calls:
grep -rn "{example}" models/

# 3. Run dbt to verify:
dbt deps && dbt compile

# dbt-lens also flags non-snake_case names, so run the score
# again after renaming to confirm the Naming score improved."""

                candidates.append(
                    FixSuggestion(
                        rank=0,
                        dimension=d.name,
                        title="Standardise model naming to snake_case",
                        explanation=(
                            "Mixed naming (CamelCase, UPPERCASE) is a red flag "
                            "for multiple authors with no agreed standard. "
                            "Rename every non-compliant model to lowercase "
                            "snake_case and update all downstream `ref()` calls."
                        ),
                        points_recoverable=d.missing,
                        affected_models=tuple(bad[:5]),
                        code_blocks=(
                            ("Bash — rename model + update refs", snippet),
                        ),
                    )
                )

        elif d.name == "Exposures":
            snippet = """\
# Add to models/exposures.yml (create if it doesn't exist)

version: 2

exposures:
  - name: weekly_revenue_dashboard
    description: "Looker Studio dashboard showing weekly revenue KPIs."
    type: dashboard
    maturity: high
    owner:
      name: Data Team
      email: data@example.com
    depends_on:
      - ref('fct_orders')
      - ref('dim_customers')
    meta:
      tool: looker
      url: "https://looker.example.com/dashboards/123" """

            candidates.append(
                FixSuggestion(
                    rank=0,
                    dimension=d.name,
                    title="Declare your downstream consumers as exposures",
                    explanation=(
                        "Exposures tell dbt which dashboards, notebooks, and "
                        "apps consume your models. With zero exposures, your "
                        "project is a black box — nobody outside the data team "
                        "knows what data is actually being used."
                    ),
                    points_recoverable=d.missing,
                    affected_models=(),
                    code_blocks=(
                        ("YAML — models/exposures.yml", snippet),
                    ),
                )
            )

        elif d.name == "Materialization maturity":
            # Find marts that look incremental-eligible but aren't
            mart_ids = {m.unique_id for m in snapshot.models if m.is_model and m.layer == "marts"}
            id_to_parents = {m.unique_id: len(m.depends_on) for m in snapshot.models if m.is_model}
            eligible = [
                m for m in snapshot.models
                if m.is_model
                and m.unique_id in mart_ids
                and m.name.lower().startswith(("fct_", "dim_"))
                and id_to_parents.get(m.unique_id, 0) >= 2
            ]
            not_inc = [m.name for m in eligible if m.materialized != "incremental"]
            top_names = not_inc[:5]

            snippet = ""
            if top_names:
                ex = top_ll[0] if (top_ll := not_inc[:1]) else "fct_orders"
                snippet = """\
# In your model .sql file, change the config:

# Before (rebuilds from scratch every run):
{{ config(materialized='table') }}

# After (appends new rows only — much faster in production):
{{ config(materialized='incremental', unique_key='id') }}

# Or in dbt_project.yml for all models in a directory:
models:
  my_project:
    marts:
      +materialized: incremental
      +unique_key: id       # ← replace with your actual PK column
      +incremental_strategy: insert_overwrite  # for BigQuery/Snowflake
"""

            candidates.append(
                FixSuggestion(
                    rank=0,
                    dimension=d.name,
                    title="Switch heavy fact tables to incremental",
                    explanation=(
                        "Fact tables with multiple upstream sources should be "
                        "`incremental` — rebuilding from scratch every run is "
                        "expensive and slow. Add `unique_key` (your PK column) "
                        "and dbt will only process new rows since the last run."
                    ),
                    points_recoverable=d.missing,
                    affected_models=tuple(top_names),
                    code_blocks=(
                        ("SQL config — switch table → incremental", snippet),
                    ) if snippet else (),
                )
            )

    candidates.sort(key=lambda c: c.points_recoverable, reverse=True)
    top = candidates[:3]
    return tuple(
        FixSuggestion(
            rank=i + 1,
            title=c.title,
            dimension=c.dimension,
            explanation=c.explanation,
            points_recoverable=c.points_recoverable,
            affected_models=c.affected_models,
            code_blocks=c.code_blocks,
        )
        for i, c in enumerate(top)
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def score_project(snapshot: ProjectSnapshot) -> HealthScore:
    """Compute a :class:`HealthScore` for a :class:`ProjectSnapshot`.

    The function is pure: the only input is the snapshot, the only output is
    the score. Calling it twice on the same input returns equal results
    (modulo float representation).
    """
    dims: list[DimensionScore] = [
        _score_test_coverage(snapshot),
        _score_documentation(snapshot),
        _score_structure(snapshot),
        _score_naming(snapshot),
        _score_exposures(snapshot),
        _score_materialization_maturity(snapshot),
    ]

    total = sum(d.earned for d in dims)
    total_clamped = max(0.0, min(TOTAL_WEIGHT, total))
    total_int = int(round(total_clamped))

    return HealthScore(
        total=total_int,
        dimensions=tuple(dims),
        fixes=_generate_fixes(tuple(dims), snapshot),
        project_name=snapshot.project_name,
        model_count=snapshot.model_count,
        source_count=len(snapshot.sources),
        test_count=len(snapshot.tests),
        exposure_count=len(snapshot.exposures),
    )


__all__ = [
    "DimensionScore",
    "FixSuggestion",
    "HealthScore",
    "score_project",
    "W_TEST_COVERAGE",
    "W_DOCUMENTATION",
    "W_STRUCTURE",
    "W_NAMING",
    "W_EXPOSURES",
    "W_MATURITY",
]
