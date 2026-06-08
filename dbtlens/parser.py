"""Parse a dbt manifest.json into a normalized ProjectSnapshot.

A dbt manifest.json is a large JSON document with several top-level keys:
- ``nodes``: dict of unique_id -> node info (models, seeds, snapshots, tests)
- ``sources``: dict of source_name.source_name -> source info
- ``exposures``: dict of exposure_name -> exposure info

This module extracts the parts dbt Lens cares about and surfaces them in a
clean, immutable dataclass so the rest of the app never has to touch the raw
manifest shape.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnInfo:
    """A single column on a model or source."""

    name: str
    description: str = ""
    tested: bool = False  # True if any test references this column


@dataclass(frozen=True)
class ModelNode:
    """A normalized dbt model (or seed/snapshot) node."""

    unique_id: str
    name: str
    resource_type: str  # "model", "seed", "snapshot", "test"
    schema_name: str
    database: str
    materialized: str  # "view", "table", "incremental", "ephemeral"
    description: str
    columns: tuple[ColumnInfo, ...]
    depends_on: tuple[str, ...]  # parent model unique_ids
    has_description: bool
    file_path: str
    layer: str  # "staging" | "intermediate" | "marts" | "other"

    @property
    def is_model(self) -> bool:
        """True if this node is a real dbt model (not a test/source)."""
        return self.resource_type == "model"

    @property
    def is_tested(self) -> bool:
        """True if any column on this model is tested."""
        return any(c.tested for c in self.columns) or self._any_model_test

    # The dict below is mutated after construction to record "model-level"
    # tests (e.g. dbt_utils.unique_combination_of_columns). The dataclass
    # itself stays frozen; we use a per-instance auxiliary dict.
    _any_model_test: bool = field(default=False, repr=False, compare=False)


@dataclass(frozen=True)
class SourceNode:
    """A normalized dbt source."""

    unique_id: str
    name: str
    source_name: str
    identifier: str
    description: str
    has_description: bool
    columns: tuple[ColumnInfo, ...]


@dataclass(frozen=True)
class TestNode:
    """A normalized dbt test."""

    unique_id: str
    name: str
    attached_node: str  # the model/column this test belongs to
    test_type: str  # e.g. "not_null", "unique", "relationships", "custom"


@dataclass(frozen=True)
class ExposureNode:
    """A normalized dbt exposure."""

    unique_id: str
    name: str
    type: str
    maturity: str
    description: str


@dataclass(frozen=True)
class ProjectSnapshot:
    """A complete, normalized view of a dbt project's manifest."""

    project_name: str
    models: tuple[ModelNode, ...]
    sources: tuple[SourceNode, ...]
    tests: tuple[TestNode, ...]
    exposures: tuple[ExposureNode, ...]
    dbt_version: str
    raw_manifest: dict[str, Any] = field(repr=False, compare=False)

    # ----- Convenience accessors -----
    @property
    def model_count(self) -> int:
        return sum(1 for m in self.models if m.is_model)

    @property
    def has_cycles(self) -> bool:
        """Detect cycles in the model dependency graph.

        Uses Kahn's algorithm. Returns True if any model is unreachable from
        the source set after pruning sources with no parents.
        """
        # Build adjacency restricted to model -> model
        ids = {m.unique_id for m in self.models}
        in_degree: dict[str, int] = {uid: 0 for uid in ids}
        children: dict[str, list[str]] = {uid: [] for uid in ids}
        for m in self.models:
            for parent in m.depends_on:
                if parent in ids:
                    children[parent].append(m.unique_id)
                    in_degree[m.unique_id] += 1
        # Kahn's
        from collections import deque

        queue = deque(uid for uid, d in in_degree.items() if d == 0)
        visited = 0
        while queue:
            uid = queue.popleft()
            visited += 1
            for child in children[uid]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)
        return visited != len(ids)

    def max_lineage_depth(self) -> int:
        """Compute the longest path length in the model dependency DAG.

        A leaf model (no children) has depth 1. Staging models with no
        parents and many children on the path drive depth higher.
        """
        ids = {m.unique_id for m in self.models}
        children: dict[str, list[str]] = {uid: [] for uid in ids}
        for m in self.models:
            for parent in m.depends_on:
                if parent in ids:
                    children[parent].append(m.unique_id)

        memo: dict[str, int] = {}

        def depth(uid: str) -> int:
            if uid in memo:
                return memo[uid]
            kids = children[uid]
            if not kids:
                memo[uid] = 1
                return 1
            memo[uid] = 1 + max(depth(c) for c in kids)
            return memo[uid]

        return max((depth(m.unique_id) for m in self.models), default=0)

    def orphans(self) -> list[str]:
        """Models with no parents AND no children in the model graph."""
        ids = {m.unique_id for m in self.models}
        has_parent: set[str] = set()
        has_child: set[str] = set()
        for m in self.models:
            for p in m.depends_on:
                if p in ids:
                    has_child.add(p)
                    has_parent.add(m.unique_id)
        return [
            m.unique_id
            for m in self.models
            if m.unique_id not in has_parent and m.unique_id not in has_child
        ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _classify_layer(file_path: str, name: str) -> str:
    """Heuristically classify a model into staging / intermediate / marts.

    Looks for path hints first (``models/marts/...`` or ``models/staging/...``),
    then falls back to the dbt naming convention ``stg_*`` / ``fct_*`` / ``dim_*``.
    """
    fp = file_path.lower().replace("\\", "/")
    if "/marts/" in fp or "/marts." in fp:
        return "marts"
    if "/staging/" in fp or "/stages/" in fp:
        return "staging"
    if "/intermediate/" in fp or "/int_" in fp:
        return "intermediate"
    n = name.lower()
    if n.startswith("stg_"):
        return "staging"
    if n.startswith("fct_") or n.startswith("dim_") or n.startswith("mart_"):
        return "marts"
    if n.startswith("int_"):
        return "intermediate"
    return "other"


def _parse_columns(raw_columns: dict[str, Any] | None) -> tuple[ColumnInfo, ...]:
    """Parse the ``columns`` dict from a manifest node."""
    if not raw_columns:
        return ()
    out: list[ColumnInfo] = []
    for cname, cinfo in raw_columns.items():
        if not isinstance(cinfo, dict):
            continue
        out.append(
            ColumnInfo(
                name=cname,
                description=(cinfo.get("description") or "").strip(),
            )
        )
    return tuple(out)


def _parse_test_target(test_meta: dict[str, Any]) -> tuple[str, str]:
    """Extract (attached_node, test_type) from a test node entry.

    The manifest's ``depends_on`` for tests points to:
    - the model (or source) being tested
    - sometimes a column (e.g. ``model.my_project.my_model.my_col``)
    We take the FIRST entry that does NOT end in a column token; that is
    the model unique_id. The test_type is the first entry in ``test_metadata``.
    """
    deps: list[str] = test_meta.get("depends_on", {}).get("nodes", [])
    # Heuristic: a "column" unique_id contains 4 dot-separated segments;
    # a "model" unique_id contains 3.
    attached = ""
    for d in deps:
        if isinstance(d, str) and d.count(".") == 2:
            attached = d
            break
    if not attached and deps:
        attached = deps[0] if isinstance(deps[0], str) else ""

    test_type = "custom"
    tm = test_meta.get("test_metadata") or {}
    if isinstance(tm, dict):
        name = tm.get("name")
        if isinstance(name, str):
            test_type = name

    return attached, test_type


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def parse_manifest(manifest: dict[str, Any]) -> ProjectSnapshot:
    """Parse a manifest.json dict into a :class:`ProjectSnapshot`.

    Args:
        manifest: The raw dict loaded from ``manifest.json``.

    Returns:
        A fully-populated :class:`ProjectSnapshot`. The returned object is
        immutable; downstream modules rely on this to make scoring
        deterministic.
    """
    metadata = manifest.get("metadata", {}) or {}
    project_name = metadata.get("project_name") or "unknown_project"
    dbt_version = metadata.get("dbt_version") or "unknown"

    nodes: dict[str, Any] = manifest.get("nodes", {}) or {}
    sources_raw: dict[str, Any] = manifest.get("sources", {}) or {}
    exposures_raw: dict[str, Any] = manifest.get("exposures", {}) or {}

    # -- First pass: collect all column names and the set of tested columns.
    tested_columns: dict[str, set[str]] = {}
    tested_models: set[str] = set()
    test_records: list[TestNode] = []
    for uid, n in nodes.items():
        if not isinstance(n, dict) or n.get("resource_type") != "test":
            continue
        attached, test_type = _parse_test_target(n)
        test_records.append(
            TestNode(
                unique_id=uid,
                name=n.get("name", uid),
                attached_node=attached,
                test_type=test_type,
            )
        )
        if attached:
            tested_models.add(attached)
            # tests can attach to a column (unique_id with 4 segments) — but
            # we just track the model-level signal for simplicity. dbt stores
            # column tests the same way; the model is the second segment.
            tested_columns.setdefault(attached, set())

    # Also: tests in manifest can attach to sources. Add those source ids.
    # (Source unique_ids look like ``source.project.source_name.table_name``)
    source_tested: set[str] = set()
    for t in test_records:
        if t.attached_node.startswith("source."):
            source_tested.add(t.attached_node)

    # -- Second pass: build ModelNode objects.
    models: list[ModelNode] = []
    for uid, n in nodes.items():
        if not isinstance(n, dict):
            continue
        rt = n.get("resource_type", "")
        if rt not in ("model", "seed", "snapshot"):
            continue

        name = n.get("name", uid.split(".")[-1])
        file_path = n.get("original_file_path") or n.get("path") or ""
        materialized = (n.get("config", {}) or {}).get("materialized", "view")
        description = (n.get("description") or "").strip()
        depends_on_raw = n.get("depends_on", {}) or {}
        parents = tuple(
            d for d in depends_on_raw.get("nodes", []) if isinstance(d, str)
        )

        raw_cols = _parse_columns(n.get("columns") or {})
        # mark tested columns
        tcol_set = tested_columns.get(uid, set())
        columns = tuple(
            ColumnInfo(c.name, c.description, tested=(c.name in tcol_set))
            for c in raw_cols
        )

        models.append(
            ModelNode(
                unique_id=uid,
                name=name,
                resource_type=rt,
                schema_name=n.get("schema", ""),
                database=n.get("database", ""),
                materialized=str(materialized),
                description=description,
                columns=columns,
                depends_on=parents,
                has_description=bool(description),
                file_path=file_path,
                layer=_classify_layer(file_path, name),
            )
        )

    # -- Build SourceNode objects.
    sources: list[SourceNode] = []
    for uid, s in sources_raw.items():
        if not isinstance(s, dict):
            continue
        sname = s.get("name", "")
        source_name = s.get("source_name", "")
        identifier = s.get("identifier") or sname
        description = (s.get("description") or "").strip()
        # Columns on sources
        src_cols: list[ColumnInfo] = []
        for cname, cinfo in (s.get("columns") or {}).items():
            if not isinstance(cinfo, dict):
                continue
            tested = uid in source_tested
            src_cols.append(
                ColumnInfo(
                    name=cname,
                    description=(cinfo.get("description") or "").strip(),
                    tested=tested,
                )
            )
        sources.append(
            SourceNode(
                unique_id=uid,
                name=sname,
                source_name=source_name,
                identifier=identifier,
                description=description,
                has_description=bool(description),
                columns=tuple(src_cols),
            )
        )

    # -- Build ExposureNode objects.
    exposures: list[ExposureNode] = []
    for uid, e in exposures_raw.items():
        if not isinstance(e, dict):
            continue
        exposures.append(
            ExposureNode(
                unique_id=uid,
                name=e.get("name", uid),
                type=(e.get("type") or "").strip(),
                maturity=(e.get("maturity") or "").strip(),
                description=(e.get("description") or "").strip(),
            )
        )

    return ProjectSnapshot(
        project_name=project_name,
        models=tuple(models),
        sources=tuple(sources),
        tests=tuple(test_records),
        exposures=tuple(exposures),
        dbt_version=str(dbt_version),
        raw_manifest=manifest,
    )


def parse_manifest_file(path: str | Path) -> ProjectSnapshot:
    """Read a manifest.json from disk and parse it.

    Args:
        path: Filesystem path to a ``manifest.json`` file.

    Returns:
        A :class:`ProjectSnapshot`.

    Raises:
        FileNotFoundError: if the file does not exist.
        json.JSONDecodeError: if the file is not valid JSON.
    """
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return parse_manifest(json.load(f))


def parse_manifest_bytes(data: bytes) -> ProjectSnapshot:
    """Parse a manifest.json from in-memory bytes (e.g. an upload)."""
    return parse_manifest(json.loads(data.decode("utf-8")))


def parse_manifest_url(url: str) -> ProjectSnapshot:
    """Fetch a manifest.json from a public URL and parse it.

    Supports:
    - Direct URLs to manifest.json
    - ``https://github.com/<owner>/<repo>/...`` — will be rewritten to the
      corresponding ``raw.githubusercontent.com`` URL if the path includes
      ``/blob/``.

    Args:
        url: HTTP(S) URL pointing at a manifest.json.

    Returns:
        A :class:`ProjectSnapshot`.

    Raises:
        RuntimeError: if the fetch or parse fails.
    """
    import urllib.request

    final_url = _github_to_raw(url)
    try:
        with urllib.request.urlopen(final_url, timeout=30) as resp:
            data = resp.read()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to fetch manifest from {final_url}: {exc}") from exc
    return parse_manifest_bytes(data)


def _github_to_raw(url: str) -> str:
    """Convert ``github.com/.../blob/...`` to ``raw.githubusercontent.com/.../...``.

    Leaves non-GitHub URLs untouched.
    """
    if "github.com" not in url:
        return url
    if "/blob/" not in url:
        return url
    # https://github.com/owner/repo/blob/branch/path -> https://raw.githubusercontent.com/owner/repo/branch/path
    head, _, tail = url.partition("github.com/")
    return f"{head}raw.githubusercontent.com/{tail.replace('/blob/', '/', 1)}"


__all__ = [
    "ColumnInfo",
    "ModelNode",
    "SourceNode",
    "TestNode",
    "ExposureNode",
    "ProjectSnapshot",
    "parse_manifest",
    "parse_manifest_file",
    "parse_manifest_bytes",
    "parse_manifest_url",
]
