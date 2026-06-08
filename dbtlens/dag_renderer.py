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
            size=28,
            font={"color": "#fff", "size": 13},
            borderWidth=2,
        )
        for n in nodes
    ]
    agraph_edges = [
        Edge(source=e.source, target=e.target, color="#94a3b8", arrows="to")
        for e in edges
    ]
    config = Config(
        width=1000,
        height=680,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        collapsible=False,
        highlightColor="#d4af37",
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script type="text/javascript" src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; font-family: 'Inter', -apple-system, sans-serif; }
  .dag-wrapper {
    position: relative;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border-radius: 16px;
    overflow: hidden;
    padding: 20px;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 25px 50px rgba(0,0,0,0.4);
  }
  .dag-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    padding: 0 4px;
  }
  .dag-title {
    color: #f8fafc;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.3px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .dag-title span { color: #d4af37; font-size: 18px; }
  .dag-badge {
    background: rgba(212,175,55,0.15);
    border: 1px solid rgba(212,175,55,0.3);
    color: #d4af37;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 20px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }
  #lens-dag {
    width: 100%; height: 580px;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,0.06);
    background: rgba(255,255,255,0.02);
  }
  .legend {
    position: absolute; top: 72px; right: 20px;
    background: rgba(15,23,42,0.92);
    backdrop-filter: blur(12px);
    padding: 16px 20px; border-radius: 12px;
    font-size: 12px;
    border: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    min-width: 220px;
    max-width: 240px;
  }
  .legend-title {
    color: #94a3b8;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .legend-row {
    display: flex;
    align-items: center;
    margin-bottom: 7px;
    color: #cbd5e1;
    font-weight: 500;
  }
  .legend-row:last-child { margin-bottom: 0; }
  .legend-dot {
    width: 10px; height: 10px; border-radius: 50%; margin-right: 9px;
    flex-shrink: 0; border: 2px solid rgba(255,255,255,0.15);
  }
  .controls {
    position: absolute; bottom: 32px; right: 32px;
    display: flex; flex-direction: column; gap: 6px;
  }
  .ctrl-btn {
    width: 34px; height: 34px; border-radius: 8px;
    background: rgba(15,23,42,0.9);
    border: 1px solid rgba(255,255,255,0.12);
    color: #94a3b8; font-size: 16px;
    cursor: pointer; display: flex; align-items: center; justify-content: center;
    transition: all 0.15s;
    backdrop-filter: blur(8px);
  }
  .ctrl-btn:hover { background: rgba(212,175,55,0.2); color: #d4af37; border-color: rgba(212,175,55,0.4); }
  .node-count {
    position: absolute; bottom: 32px; left: 32px;
    background: rgba(15,23,42,0.9);
    border: 1px solid rgba(255,255,255,0.1);
    color: #64748b; font-size: 12px; font-weight: 500;
    padding: 8px 14px; border-radius: 20px;
    backdrop-filter: blur(8px);
  }
  /* Kill vis-network's built-in nav buttons — we use our own controls */
  .vis-navigation { display: none !important; }
  .vis-zoom-actions { display: none !important; }
</style>
</head>
<body>
<div class="dag-wrapper">
  <div class="dag-header">
    <div class="dag-title"><span>🔬</span> dbt Lens — Project DAG</div>
    <div class="dag-badge">Interactive</div>
  </div>
  <div id="lens-dag"></div>
  <div class="legend">
    <div class="legend-title">Model Health</div>
    <div class="legend-row"><div class="legend-dot" style="background:#22c55e;border-color:#16a34a"></div> Healthy (tested & documented)</div>
    <div class="legend-row"><div class="legend-dot" style="background:#eab308;border-color:#ca8a04"></div> Tests only</div>
    <div class="legend-row"><div class="legend-dot" style="background:#f97316;border-color:#ea580c"></div> Docs only</div>
    <div class="legend-row"><div class="legend-dot" style="background:#ef4444;border-color:#dc2626"></div> Neither</div>
    <div class="legend-row"><div class="legend-dot" style="background:#3b82f6;border-color:#2563eb"></div> Source</div>
    <div class="legend-row"><div class="legend-dot" style="background:#a855f7;border-color:#9333ea"></div> Exposure</div>
  </div>
  <div class="controls">
    <button class="ctrl-btn" onclick="network.zoomIn()" title="Zoom in">+</button>
    <button class="ctrl-btn" onclick="network.zoomOut()" title="Zoom out">−</button>
    <button class="ctrl-btn" onclick="network.fit({animation:{duration:500,easingFunction:'easeInOutQuad'}})" title="Fit">⊡</button>
  </div>
  <div class="node-count" id="nodeCount"></div>
</div>
<script type="text/javascript">
  var data = __DATA__;
  var container = document.getElementById('lens-dag');
  document.getElementById('nodeCount').textContent = data.nodes.length + ' nodes · ' + data.edges.length + ' edges';
  var options = {
    nodes: {
      borderWidth: 2,
      shadow: { enabled: true, color: 'rgba(0,0,0,0.4)', size: 8, x: 0, y: 3 },
      font: { color: '#fff', size: 13, face: 'Inter, -apple-system, sans-serif', strokeWidth: 3, strokeColor: 'rgba(15,23,42,0.8)' },
      margin: { top: 8, right: 12, bottom: 8, left: 12 },
    },
    edges: {
      color: { color: 'rgba(148,163,184,0.4)', highlight: '#d4af37', hover: '#d4af37' },
      width: 1.5,
      arrows: { to: { enabled: true, scaleFactor: 0.6 } },
      smooth: { type: 'cubicBezier', roundness: 0.3 }
    },
    physics: {
      enabled: true,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: { gravitationalConstant: -50, springLength: 130, springConstant: 0.08, damping: 0.4 },
      stabilization: { iterations: 250 }
    },
    interaction: {
      hover: true,
      tooltipDelay: 80,
      zoomView: true,
      dragView: true,
      keyboard: true,
      navigationButtons: false
    }
  };
  var network = new vis.Network(container, data, options);
  network.once('stabilizationIterationsDone', function() { network.setOptions({ physics: { enabled: false } }); });
  network.on('hoverNode', function(props) {
    document.body.style.cursor = 'pointer';
  });
  network.on('blurrNode', function(props) {
    document.body.style.cursor = 'default';
  });
</script>
</body>
</html>
"""


_HEALTH_BORDER = {
    HEALTHY: "#16a34a",
    SEMI_DOC: "#ca8a04",
    SEMI_TEST: "#ea580c",
    UNHEALTHY: "#dc2626",
    SOURCE: "#2563eb",
    EXPOSURE: "#9333ea",
}


def render_with_vis_html(
    nodes: list[DagNode], edges: list[DagEdge]
) -> str:
    """Build a self-contained HTML string for the vis-network DAG."""
    payload = {
        "nodes": [
            {
                "id": n.id,
                "label": f"<b>{n.label}</b>",
                "color": {
                    "background": n.color,
                    "border": _HEALTH_BORDER.get(n.id.split(".")[0], n.color),
                    "highlight": {"background": n.color, "border": "#d4af37"},
                },
                "borderWidth": 2,
                "borderWidthSelected": 3,
                "font": {
                    "color": "#f8fafc",
                    "size": 13,
                    "face": "Inter, -apple-system, sans-serif",
                    "strokeWidth": 3,
                    "strokeColor": "rgba(15,23,42,0.9)",
                },
                "shadow": {"enabled": True, "color": "rgba(0,0,0,0.5)", "size": 10, "x": 0, "y": 4},
                "title": n.title,
                "shape": n.shape,
                "size": 22,
                "margin": {"top": 8, "right": 12, "bottom": 8, "left": 12},
            }
            for n in nodes
        ],
        "edges": [
            {
                "from": e.source,
                "to": e.target,
                "color": {"color": "rgba(148,163,184,0.5)", "highlight": "#d4af37", "hover": "#d4af37"},
                "width": 1.5,
                "arrows": {"to": {"enabled": True, "scaleFactor": 0.6}},
            }
            for e in edges
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
    st.components.v1.html(html, height=720, scrolling=False)


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
