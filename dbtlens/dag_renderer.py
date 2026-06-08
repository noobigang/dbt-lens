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
# d3-dag renderer — hierarchical (sugiyama) layout, no backward arrows
# ---------------------------------------------------------------------------

# Health colors (fill, border)
_HEALTH_FILL = {
    HEALTHY: "#22c55e",
    SEMI_DOC: "#eab308",
    SEMI_TEST: "#f97316",
    UNHEALTHY: "#ef4444",
    SOURCE: "#3b82f6",
    EXPOSURE: "#a855f7",
}
_HEALTH_BORDER = {
    HEALTHY: "#16a34a",
    SEMI_DOC: "#ca8a04",
    SEMI_TEST: "#ea580c",
    UNHEALTHY: "#dc2626",
    SOURCE: "#2563eb",
    EXPOSURE: "#9333ea",
}
_HEALTH_TEXT = {
    HEALTHY: "#f0fdf4",
    SEMI_DOC: "#1c1917",
    SEMI_TEST: "#fff7ed",
    UNHEALTHY: "#fef2f2",
    SOURCE: "#eff6ff",
    EXPOSURE: "#faf5ff",
}


_DAG_HTML = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-dag@0.11.1/bundle/d3-dag.cjs.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; font-family: 'Inter', -apple-system, sans-serif; }

  .dag-wrapper {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border-radius: 16px;
    overflow: hidden;
    padding: 20px;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 25px 50px rgba(0,0,0,0.4);
    display: flex;
    flex-direction: column;
    height: 100%;
  }
  .dag-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
    flex-shrink: 0;
  }
  .dag-title {
    color: #f8fafc;
    font-size: 15px;
    font-weight: 600;
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

  #lens-dag-container {
    flex: 1;
    position: relative;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,0.06);
    background: rgba(255,255,255,0.02);
    overflow: hidden;
  }
  #lens-dag { width: 100%; height: 100%; }
  #lens-dag svg { display: block; }

  .legend {
    position: absolute; top: 14px; right: 14px;
    background: rgba(15,23,42,0.94);
    backdrop-filter: blur(12px);
    padding: 14px 18px; border-radius: 12px;
    font-size: 11.5px;
    border: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 8px 24px rgba(0,0,0,0.35);
    min-width: 210px;
    z-index: 10;
  }
  .legend-title {
    color: #94a3b8;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .legend-row {
    display: flex; align-items: center; margin-bottom: 7px; color: #cbd5e1; font-weight: 500;
  }
  .legend-row:last-child { margin-bottom: 0; }
  .legend-dot {
    width: 10px; height: 10px; border-radius: 3px; margin-right: 9px; flex-shrink: 0;
  }

  .controls {
    position: absolute; bottom: 14px; right: 14px;
    display: flex; flex-direction: column; gap: 5px; z-index: 10;
  }
  .ctrl-btn {
    width: 34px; height: 34px; border-radius: 8px;
    background: rgba(15,23,42,0.92);
    border: 1px solid rgba(255,255,255,0.12);
    color: #94a3b8; font-size: 16px;
    cursor: pointer; display: flex; align-items: center; justify-content: center;
    transition: all 0.15s; backdrop-filter: blur(8px);
    user-select: none;
  }
  .ctrl-btn:hover { background: rgba(212,175,55,0.2); color: #d4af37; border-color: rgba(212,175,55,0.4); }

  .node-count {
    position: absolute; bottom: 14px; left: 14px;
    background: rgba(15,23,42,0.9);
    border: 1px solid rgba(255,255,255,0.1);
    color: #64748b; font-size: 11px; font-weight: 500;
    padding: 7px 12px; border-radius: 20px;
    backdrop-filter: blur(8px); z-index: 10;
  }

  /* Node styles */
  .node-group { cursor: pointer; }
  .node-group:hover .node-box { filter: brightness(1.15); }
  .node-box { transition: filter 0.15s; }
  .node-label { font-size: 12px; font-weight: 500; fill: white; pointer-events: none; }
  .edge-path { fill: none; stroke: rgba(148,163,184,0.45); stroke-width: 1.5px; }
  .edge-path:hover { stroke: #d4af37; stroke-width: 2px; }
  .arrowhead { fill: rgba(148,163,184,0.6); }
</style>
</head>
<body>
<div class="dag-wrapper">
  <div class="dag-header">
    <div class="dag-title"><span>🔬</span> dbt Lens — Project DAG</div>
    <div class="dag-badge">Hierarchical · Sugiyama layout</div>
  </div>
  <div id="lens-dag-container">
    <svg id="lens-dag"></svg>
    <div class="legend">
      <div class="legend-title">Model Health</div>
      <div class="legend-row"><div class="legend-dot" style="background:#22c55e"></div> Tested & documented</div>
      <div class="legend-row"><div class="legend-dot" style="background:#eab308"></div> Tests only</div>
      <div class="legend-row"><div class="legend-dot" style="background:#f97316"></div> Docs only</div>
      <div class="legend-row"><div class="legend-dot" style="background:#ef4444"></div> Neither tested nor documented</div>
      <div class="legend-row"><div class="legend-dot" style="background:#3b82f6"></div> Source</div>
      <div class="legend-row"><div class="legend-dot" style="background:#a855f7"></div> Exposure</div>
    </div>
    <div class="controls">
      <button class="ctrl-btn" id="zoomIn" title="Zoom in">+</button>
      <button class="ctrl-btn" id="zoomOut" title="Zoom out">−</button>
      <button class="ctrl-btn" id="zoomFit" title="Fit">⊡</button>
    </div>
    <div class="node-count" id="nodeCount"></div>
  </div>
</div>
<script type="text/javascript">
  var rawData = __DATA__;
  var nodeMap = {};
  rawData.nodes.forEach(function(n) { nodeMap[n.id] = n; });

  var container = document.getElementById('lens-dag-container');
  var svgEl = document.getElementById('lens-dag');
  var W = container.clientWidth || 900;
  var H = container.clientHeight || 600;

  var svg = d3.select('#lens-dag').attr('width', W).attr('height', H);
  svg.selectAll('*').remove();

  // Build node list for d3-dag stratify
  // Each node needs: id, parentIds (empty array for roots)
  var nodeIds = new Set(rawData.nodes.map(function(n) { return n.id; }));
  var dagNodes = rawData.nodes.map(function(n) {
    return { id: n.id };
  });

  // Build edges as parentIds format
  var parentMap = {};
  rawData.edges.forEach(function(e) {
    if (!parentMap[e.target]) parentMap[e.target] = [];
    parentMap[e.target].push(e.source);
  });

  // Create dagNodes with parentIds
  var dagInput = rawData.nodes.map(function(n) {
    return {
      id: n.id,
      parentIds: parentMap[n.id] || []
    };
  });

  // Handle nodes with no edges (root orphans) — give them no parentIds
  dagInput.forEach(function(n) {
    if (n.parentIds.length === 0 && rawData.edges.length > 0) {
      // Check if this node appears as a source or target in edges
      var hasEdge = rawData.edges.some(function(e) {
        return e.source === n.id || e.target === n.id;
      });
      if (!hasEdge && rawData.edges.length > 0) {
        // Orphan node — keep parentIds empty, it will be a root
      }
    }
  });

  // Build DAG using d3-dag 0.11.1 CJS bundle
  // API: d3dag.stratify() and d3dag.sugiyama() (not d3.dagStratify)
  var stratify = d3dag.stratify();
  var dag;
  try {
    dag = stratify(dagInput);
  } catch(e) {
    console.error('d3-dag stratify error:', e);
    document.getElementById('nodeCount').textContent = 'DAG error: ' + e.message;
    dag = null;
  }

  if (dag) {
    // Sugiyama layout — clean hierarchical left-to-right
    // d3-dag 0.11.1 API: sugiyama().nodeSize([w,h]).layering().decross().coord()
    var layout = d3dag.sugiyama()
      .nodeSize(function(n) { return [140, 48]; })
      .layering(d3dag.layeringSimplex())
      .decross(d3dag.decrossOpt())
      .coord(d3dag.coordQuad());

    layout(dag);

    // Zoom behavior
    var zoom = d3.zoom().scaleExtent([0.25, 2.5]).on('zoom', function(event) {
      g.attr('transform', event.transform);
    });
    svg.call(zoom);

    var g = svg.append('g').attr('transform', 'translate(50, 20)');

    // Arrow marker definition
    svg.append('defs').append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 7)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('class', 'arrowhead');

    // Draw edges using link points from d3-dag
    g.append('g').attr('class', 'edges')
      .selectAll('path')
      .data(dag.links())
      .enter()
      .append('path')
      .attr('class', 'edge-path')
      .attr('d', function(link) {
        var pts = link.points;
        if (!pts || pts.length < 2) return '';
        var start = pts[0];
        var end = pts[pts.length - 1];
        return 'M' + start.x + ',' + start.y +
               ' C' + (start.x + 50) + ',' + start.y +
               ' ' + (end.x - 50) + ',' + end.y +
               ' ' + end.x + ',' + end.y;
      })
      .attr('marker-end', 'url(#arrow)');

    // Draw nodes
    var allNodes = dag.nodes ? dag.nodes() : dag.descendants();

    var nodeGroups = g.append('g').attr('class', 'nodes')
      .selectAll('g')
      .data(allNodes)
      .enter()
      .append('g')
      .attr('class', 'node-group')
      .attr('transform', function(n) {
        return 'translate(' + n.x + ',' + n.y + ')';
      });

    // Node rect
    nodeGroups.append('rect')
      .attr('class', 'node-box')
      .attr('x', -70).attr('y', -24)
      .attr('width', 140).attr('height', 48)
      .attr('rx', 10)
      .attr('fill', function(n) {
        var nd = nodeMap[n.id] || {};
        return nd.color || '#64748b';
      })
      .attr('stroke', function(n) {
        var nd = nodeMap[n.id] || {};
        var c = nd.color || '#64748b';
        return d3.color(c).darker(0.6);
      })
      .attr('stroke-width', 2);

    // Node label
    nodeGroups.append('text')
      .attr('class', 'node-label')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('y', 0)
      .text(function(n) {
        var label = (nodeMap[n.id] || {}).label || n.id;
        return label.length > 16 ? label.substring(0, 14) + '…' : label;
      });

    // Tooltip
    nodeGroups.append('title').text(function(n) {
      var nd = nodeMap[n.id] || {};
      return nd.title || nd.label || n.id;
    });

    document.getElementById('nodeCount').textContent =
      rawData.nodes.length + ' nodes · ' + rawData.edges.length + ' edges';
  }

  // Zoom controls
  document.getElementById('zoomIn').addEventListener('click', function() {
    svg.transition().duration(300).call(zoom.scaleBy, 1.3);
  });
  document.getElementById('zoomOut').addEventListener('click', function() {
    svg.transition().duration(300).call(zoom.scaleBy, 0.75);
  });
  document.getElementById('zoomFit').addEventListener('click', function() {
    svg.transition().duration(400).call(zoom.transform, d3.zoomIdentity);
  });
</script>
</body>
</html>
"""


def render_with_vis_html(
    nodes: list[DagNode], edges: list[DagEdge]
) -> str:
    """Build a self-contained HTML string using d3-dag with sugiyama layout."""
    payload = {
        "nodes": [
            {
                "id": n.id,
                "label": n.label,
                "color": n.color,
                "title": n.title,
            }
            for n in nodes
        ],
        "edges": [
            {"source": e.source, "target": e.target}
            for e in edges
        ],
    }
    return _DAG_HTML.replace("__DATA__", json.dumps(payload))


# ---------------------------------------------------------------------------
# Streamlit dispatcher
# ---------------------------------------------------------------------------


def render_dag(snapshot: ProjectSnapshot) -> None:
    """Render the DAG inside a Streamlit app.

    Uses d3-dag with the sugiyama algorithm for clean hierarchical
    left-to-right layout. Rendered as a self-contained HTML block
    via st.components.v1.html.
    """
    import streamlit as st

    nodes, edges = build_dag(snapshot)
    if not nodes:
        st.info("No models in this manifest to render.")
        return

    html = render_with_vis_html(nodes, edges)
    st.components.v1.html(html, height=750, scrolling=False)


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
