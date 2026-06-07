"""Render an interactive DAG colored by per-model health.

The renderer tries (in order):
1. ``streamlit-agraph`` — the preferred networkx-of-agraph embedded component
2. A hand-rolled ``st.components.v1.html`` block using vis-network loaded
   from a CDN

The output is a self-contained HTML fragment. The Streamlit app calls
:func:`render_dag` and we choose whichever backend imports cleanly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .parser import ModelNode, ProjectSnapshot


# ---------------------------------------------------------------------------
# Per-model health classification
# ---------------------------------------------------------------------------

# Health buckets — the colors are also used by the share card
HEALTHY = "healthy"  # has tests AND docs
SEMI_DOC = "semi_doc"  # has tests but missing docs
SEMI_TEST = "semi_test"  # has docs but missing tests
UNHEALTHY = "unhealthy"  # missing both
SOURCE = "source"  # source node
EXPOSURE = "exposure"  # exposure node


_HEALTH_COLOR = {
    HEALTHY: "#22c55e",  # green
    SEMI_DOC: "#eab308",  # yellow
    SEMI_TEST: "#f97316",  # orange
    UNHEALTHY: "#ef4444",  # red
    SOURCE: "#3b82f6",  # blue
    EXPOSURE: "#a855f7",  # purple
}


@dataclass(frozen=True)
class DagNode:
    """A single node in the rendered DAG."""

    id: str
    label: str
    color: str
    title: str  # hover tooltip
    shape: str = "box"


@dataclass(frozen=True)
class DagEdge:
    """A single edge in the rendered DAG."""

    source: str
    target: str
    arrows: str = "to"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _tested_model_ids(snapshot: ProjectSnapshot) -> set[str]:
    return {t.attached_node for t in snapshot.tests}


def _classify_model(m: ModelNode, tested: set[str]) -> str:
    has_tests = m.unique_id in tested
    has_docs = m.has_description and all(c.description.strip() for c in m.columns)
    if has_tests and has_docs:
        return HEALTHY
    if has_tests and not has_docs:
        return SEMI_DOC
    if not has_tests and has_docs:
        return SEMI_TEST
    return UNHEALTHY


def _build_tooltip(m: ModelNode) -> str:
    """Build a multi-line hover tooltip for a model node."""
    lines: list[str] = [
        f"<b>{m.name}</b>",
        f"layer: {m.layer}",
        f"materialization: {m.materialized}",
    ]
    if m.description:
        # escape minimal HTML
        esc = m.description.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"<br/>{esc[:200]}{'...' if len(m.description) > 200 else ''}")
    if m.columns:
        tested = sum(1 for c in m.columns if c.tested)
        lines.append(f"<br/>{tested}/{len(m.columns)} columns tested")
    return "\n".join(lines)


def build_dag(snapshot: ProjectSnapshot) -> tuple[list[DagNode], list[DagEdge]]:
    """Translate a ProjectSnapshot into nodes/edges ready for the renderer.

    Args:
        snapshot: A :class:`ProjectSnapshot` from :mod:`parser`.

    Returns:
        A tuple ``(nodes, edges)``. The renderer is responsible for
        formatting them for its particular backend.
    """
    nodes: list[DagNode] = []
    edges: list[DagEdge] = []
    tested = _tested_model_ids(snapshot)

    # -- Models --
    for m in snapshot.models:
        if not m.is_model:
            continue
        health = _classify_model(m, tested)
        nodes.append(
            DagNode(
                id=m.unique_id,
                label=m.name,
                color=_HEALTH_COLOR[health],
                title=_build_tooltip(m),
            )
        )
        for parent in m.depends_on:
            edges.append(DagEdge(source=parent, target=m.unique_id))

    # -- Sources (light blue squares; no incoming edges) --
    for s in snapshot.sources:
        nodes.append(
            DagNode(
                id=s.unique_id,
                label=f"{s.source_name}.{s.name}",
                color=_HEALTH_COLOR[SOURCE],
                title=f"<b>{s.source_name}.{s.name}</b><br/>source",
                shape="ellipse",
            )
        )
        # Sources link into the project via tests. We don't model data flow
        # edges for sources; tests are visible on the models they attach to.

    # -- Exposures (purple diamonds) --
    for e in snapshot.exposures:
        nodes.append(
            DagNode(
                id=e.unique_id,
                label=f"📊 {e.name}",
                color=_HEALTH_COLOR[EXPOSURE],
                title=f"<b>{e.name}</b><br/>exposure ({e.type or 'unspecified'})",
                shape="diamond",
            )
        )
        # Exposures point at their depends_on nodes (often a mart).
        # The parser keeps raw manifest; we re-derive here.
        deps = (
            snapshot.raw_manifest.get("exposures", {})
            .get(e.unique_id, {})
            .get("depends_on", {})
            .get("nodes", [])
        )
        for parent in deps:
            edges.append(DagEdge(source=parent, target=e.unique_id))

    return nodes, edges


# ---------------------------------------------------------------------------
# streamlit-agraph backend
# ---------------------------------------------------------------------------


def render_with_agraph(nodes: list[DagNode], edges: list[DagEdge]) -> Any:
    """Render via streamlit-agraph. Returns the agraph component instance.

    Imported lazily so the module loads even if agraph is not installed.
    """
    from streamlit_agraph import Config, Edge, Node, agraph

    agraph_nodes = [
        Node(
            id=n.id,
            label=n.label,
            color=n.color,
            title=n.title,
            shape=n.shape,
            size=25,
            font={"color": "#111", "size": 14},
        )
        for n in nodes
    ]
    agraph_edges = [
        Edge(source=e.source, target=e.target, color="#94a3b8", arrows="to")
        for e in edges
    ]
    config = Config(
        width=1000,
        height=650,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        collapsible=False,
        highlightColor="#F7A7A6",
        maxZoom=2.5,
        minZoom=0.3,
    )
    return agraph(nodes=agraph_nodes, edges=agraph_edges, config=config)


# ---------------------------------------------------------------------------
# Fallback: vis-network via st.components.v1.html
# ---------------------------------------------------------------------------


_VIS_HTML = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<script type="text/javascript" src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
  #lens-dag { width: 100%; height: 650px; border: 1px solid #e5e7eb; border-radius: 8px; }
  .legend {
    position: absolute; top: 12px; right: 12px; background: white;
    padding: 10px 14px; border-radius: 8px; font-family: -apple-system, system-ui, sans-serif;
    font-size: 13px; box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  }
  .legend .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
</style>
</head>
<body>
<div style="position: relative;">
  <div id="lens-dag"></div>
  <div class="legend">
    <div><span class="dot" style="background:#22c55e"></span> Healthy</div>
    <div><span class="dot" style="background:#eab308"></span> Tests only</div>
    <div><span class="dot" style="background:#f97316"></span> Docs only</div>
    <div><span class="dot" style="background:#ef4444"></span> Untested & undocumented</div>
    <div><span class="dot" style="background:#3b82f6"></span> Source</div>
    <div><span class="dot" style="background:#a855f7"></span> Exposure</div>
  </div>
</div>
<script type="text/javascript">
  var data = __DATA__;
  var container = document.getElementById('lens-dag');
  var options = {
    nodes: {
      shape: 'box',
      margin: 10,
      font: { color: '#111', size: 14, face: '-apple-system, system-ui, sans-serif' }
    },
    edges: {
      color: '#94a3b8',
      arrows: { to: { enabled: true, scaleFactor: 0.5 } },
      smooth: { type: 'continuous' }
    },
    physics: {
      enabled: true,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: { gravitationalConstant: -45, springLength: 110, springConstant: 0.08 },
      stabilization: { iterations: 200 }
    },
    interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true }
  };
  var network = new vis.Network(container, data, options);
  network.once('stabilizationIterationsDone', function() { network.setOptions({ physics: false }); });
</script>
</body>
</html>
"""


def render_with_vis_html(
    nodes: list[DagNode], edges: list[DagEdge]
) -> str:
    """Build a self-contained HTML string for the vis-network DAG."""
    payload = {
        "nodes": [
            {
                "id": n.id,
                "label": n.label,
                "color": {"background": n.color, "border": n.color},
                "title": n.title,
                "shape": n.shape,
            }
            for n in nodes
        ],
        "edges": [
            {"from": e.source, "to": e.target} for e in edges
        ],
    }
    return _VIS_HTML.replace("__DATA__", json.dumps(payload))


# ---------------------------------------------------------------------------
# Streamlit dispatcher
# ---------------------------------------------------------------------------


def render_dag(snapshot: ProjectSnapshot) -> None:
    """Render the DAG inside a Streamlit app.

    Tries ``streamlit-agraph`` first. Falls back to a self-contained
    ``vis-network`` HTML block via ``st.components.v1.html``.
    """
    import streamlit as st

    nodes, edges = build_dag(snapshot)
    if not nodes:
        st.info("No models in this manifest to render.")
        return

    try:
        render_with_agraph(nodes, edges)
        return
    except Exception as exc:  # noqa: BLE001
        st.warning(
            f"streamlit-agraph not available ({exc.__class__.__name__}). "
            "Falling back to embedded vis-network."
        )

    html = render_with_vis_html(nodes, edges)
    st.components.v1.html(html, height=700, scrolling=False)


__all__ = [
    "DagNode",
    "DagEdge",
    "build_dag",
    "render_dag",
    "render_with_agraph",
    "render_with_vis_html",
    "HEALTHY",
    "SEMI_DOC",
    "SEMI_TEST",
    "UNHEALTHY",
    "SOURCE",
    "EXPOSURE",
    "_HEALTH_COLOR",
]
