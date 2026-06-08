"""Render an interactive DAG colored by per-model health.

Uses dagre.js for clean hierarchical left-to-right layout,
rendered as pure SVG via st.components.v1.html.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .parser import ModelNode, ProjectSnapshot


# ---------------------------------------------------------------------------
# Per-model health classification
# ---------------------------------------------------------------------------

HEALTHY = "healthy"
SEMI_DOC = "semi_doc"
SEMI_TEST = "semi_test"
UNHEALTHY = "unhealthy"
SOURCE = "source"
EXPOSURE = "exposure"

_HEALTH_COLOR = {
    HEALTHY: "#22c55e",
    SEMI_DOC: "#eab308",
    SEMI_TEST: "#f97316",
    UNHEALTHY: "#ef4444",
    SOURCE: "#3b82f6",
    EXPOSURE: "#a855f7",
}


@dataclass(frozen=True)
class DagNode:
    id: str
    label: str
    color: str
    title: str
    shape: str = "box"


@dataclass(frozen=True)
class DagEdge:
    source: str
    target: str


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
    lines: list[str] = [
        f"<b>{m.name}</b>",
        f"layer: {m.layer}",
        f"materialization: {m.materialized}",
    ]
    if m.description:
        esc = m.description.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"<br/>{esc[:200]}{'...' if len(m.description) > 200 else ''}")
    if m.columns:
        tested = sum(1 for c in m.columns if c.tested)
        lines.append(f"<br/>{tested}/{len(m.columns)} columns tested")
    return "\n".join(lines)


def build_dag(snapshot: ProjectSnapshot) -> tuple[list[DagNode], list[DagEdge]]:
    nodes: list[DagNode] = []
    edges: list[DagEdge] = []
    tested = _tested_model_ids(snapshot)

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

    for e in snapshot.exposures:
        nodes.append(
            DagNode(
                id=e.unique_id,
                label=f"{e.name}",
                color=_HEALTH_COLOR[EXPOSURE],
                title=f"<b>{e.name}</b><br/>exposure ({e.type or 'unspecified'})",
                shape="diamond",
            )
        )
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
# HTML renderer using dagre.js (proven clean DAG layout)
# ---------------------------------------------------------------------------

_DAG_HTML = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dagre@0.8.5/dist/dagre.min.js"></script>
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
    position: relative;
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

  /* SVG node styles */
  .node-group { cursor: pointer; }
  .node-group:hover .node-box { filter: brightness(1.2); }
  .node-label { font-size: 11px; font-weight: 500; fill: white; pointer-events: none; font-family: 'Inter', sans-serif; letter-spacing: 0.2px; }
  .edge-path { fill: none; stroke: #475569; stroke-width: 1.5px; }
  .edge-path:hover { stroke: #d4af37; stroke-width: 2.5px; }
  .arrow-marker { fill: #475569; }
</style>
</head>
<body>
<div class="dag-wrapper">
  <div class="dag-header">
    <div class="dag-title"><span>🔬</span> dbt Lens — Project DAG</div>
    <div class="dag-badge">Dagre Layout · Left-to-Right</div>
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
(function() {
  var rawData = __DATA__;
  var nodeMap = {};
  rawData.nodes.forEach(function(n) { nodeMap[n.id] = n; });

  var container = document.getElementById('lens-dag-container');
  var W = container.clientWidth || 900;
  var H = container.clientHeight || 650;

  var svg = d3.select('#lens-dag')
    .attr('width', W)
    .attr('height', H);

  svg.selectAll('*').remove();

  // Arrow marker
  var defs = svg.append('defs');
  defs.append('marker')
    .attr('id', 'arrow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 6)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('class', 'arrow-marker');

  defs.append('marker')
    .attr('id', 'arrow-hover')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 6)
    .attr('refY', 0)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#d4af37');

  // Build dagre graph — clean left-to-right layout
  var g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: 'LR',
    nodesep: 50,
    ranksep: 80,
    marginx: 60,
    marginy: 60,
    edgesep: 10,
    ranker: 'tight-sidebar'
  });
  g.setDefaultEdgeLabel(function() { return {}; });

  // Add nodes to dagre — wider nodes prevent label truncation
  rawData.nodes.forEach(function(n) {
    var isSource = n.shape === 'ellipse';
    var isExposure = n.shape === 'diamond';
    var w = isSource || isExposure ? 150 : 170;
    var h = 40;
    g.setNode(n.id, { width: w, height: h });
  });

  // Add edges to dagre
  rawData.edges.forEach(function(e) {
    if (g.hasNode(e.source) && g.hasNode(e.target)) {
      g.setEdge(e.source, e.target);
    }
  });

  // Run dagre layout
  dagre.layout(g);

  // Compute bounding box of all nodes
  var allNodes = g.nodes();
  var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  allNodes.forEach(function(nid) {
    var info = g.node(nid);
    var x = info.x, y = info.y, w = info.width, h = info.height;
    minX = Math.min(minX, x - w/2);
    minY = Math.min(minY, y - h/2);
    maxX = Math.max(maxX, x + w/2);
    maxY = Math.max(maxY, y + h/2);
  });

  var graphW = maxX - minX + 80;
  var graphH = maxY - minY + 80;
  var offsetX = 50 - minX;
  var offsetY = 30 - minY;

  // Create main group with zoom
  var zoom = d3.zoom()
    .scaleExtent([0.2, 2.5])
    .on('zoom', function(event) {
      mainGroup.attr('transform', event.transform);
    });
  svg.call(zoom);
  svg.on('dblclick.zoom', null);

  var mainGroup = svg.append('g').attr('class', 'main-group');

  // Zoom control buttons
  document.getElementById('zoomIn').addEventListener('click', function() {
    svg.transition().duration(300).call(zoom.scaleBy, 1.4);
  });
  document.getElementById('zoomOut').addEventListener('click', function() {
    svg.transition().duration(300).call(zoom.scaleBy, 0.7);
  });
  document.getElementById('zoomFit').addEventListener('click', function() {
    svg.transition().duration(400).call(zoom.transform, d3.zoomIdentity);
  });

  // Draw edges
  var edgeGroup = mainGroup.append('g').attr('class', 'edges');
  g.edges().forEach(function(e) {
    var edgeInfo = g.edge(e);
    var points = edgeInfo.points;
    if (!points || points.length < 2) return;

    // Offset points
    var offsetPoints = points.map(function(p) {
      return { x: p.x + offsetX, y: p.y + offsetY };
    });

    // Build smooth path
    var pathStr = buildSmoothPath(offsetPoints);

    var edgeEl = edgeGroup.append('path')
      .attr('class', 'edge-path')
      .attr('d', pathStr)
      .attr('marker-end', 'url(#arrow)');

    edgeEl.on('mouseover', function() {
      d3.select(this)
        .attr('stroke', '#d4af37')
        .attr('stroke-width', 2.5)
        .attr('marker-end', 'url(#arrow-hover)');
    });
    edgeEl.on('mouseout', function() {
      d3.select(this)
        .attr('stroke', '#475569')
        .attr('stroke-width', 1.5)
        .attr('marker-end', 'url(#arrow)');
    });
  });

  // Draw nodes
  var nodeGroup = mainGroup.append('g').attr('class', 'nodes');
  allNodes.forEach(function(nid) {
    var info = g.node(nid);
    var ndata = nodeMap[nid] || {};
    var shape = ndata.shape || 'box';
    var color = ndata.color || '#64748b';
    var label = ndata.label || nid;
    var title = ndata.title || '';
    var x = info.x + offsetX;
    var y = info.y + offsetY;
    var w = info.width;
    var h = info.height;

    var darker = d3.color(color).darker(0.5);

    var ng = nodeGroup.append('g')
      .attr('class', 'node-group')
      .attr('transform', 'translate(' + x + ',' + y + ')');

    if (shape === 'ellipse') {
      ng.append('ellipse')
        .attr('rx', w/2 + 6)
        .attr('ry', h/2 + 4)
        .attr('fill', color)
        .attr('stroke', darker)
        .attr('stroke-width', 1.5)
        .attr('filter', 'url(#node-shadow)');
    } else if (shape === 'diamond') {
      var points = [
        [0, -h/2 - 4],
        [w/2 + 6, 0],
        [0, h/2 + 4],
        [-w/2 - 6, 0]
      ].map(function(p) { return p[0] + ',' + p[1]; }).join(' ');
      ng.append('polygon')
        .attr('points', points)
        .attr('fill', color)
        .attr('stroke', darker)
        .attr('stroke-width', 1.5);
    } else {
      ng.append('rect')
        .attr('x', -w/2 - 4)
        .attr('y', -h/2 - 4)
        .attr('width', w + 8)
        .attr('height', h + 8)
        .attr('rx', 12)
        .attr('fill', color)
        .attr('stroke', darker)
        .attr('stroke-width', 2);
    }

    // Label — allow more characters with wider nodes + smaller font
    ng.append('text')
      .attr('class', 'node-label')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('y', 1)
      .text(label.length > 20 ? label.substring(0, 18) + '…' : label);

    // Tooltip
    ng.append('title').text(title || label);
  });

  // Node shadow filter
  defs.append('filter')
    .attr('id', 'node-shadow')
    .attr('x', '-20%').attr('y', '-20%')
    .attr('width', '140%').attr('height', '140%')
    .append('feDropShadow')
    .attr('dx', 0).attr('dy', 2)
    .attr('stdDeviation', 4)
    .attr('flood-color', 'rgba(0,0,0,0.4)');

  // Helper: build smooth orthogonal path
  function buildSmoothPath(points) {
    if (points.length < 2) return '';
    var parts = [];
    parts.push('M' + points[0].x + ',' + points[0].y);

    for (var i = 1; i < points.length - 1; i++) {
      var prev = points[i - 1];
      var curr = points[i];
      var next = points[i + 1];
      var r = 8;
      // Limit radius to half the shorter segment
      var d1 = Math.sqrt(Math.pow(curr.x - prev.x, 2) + Math.pow(curr.y - prev.y, 2));
      var d2 = Math.sqrt(Math.pow(next.x - curr.x, 2) + Math.pow(next.y - curr.y, 2));
      r = Math.min(r, d1 / 2, d2 / 2);

      var dx1 = curr.x - prev.x, dy1 = curr.y - prev.y;
      var dx2 = next.x - curr.x, dy2 = next.y - curr.y;
      var len1 = Math.sqrt(dx1*dx1 + dy1*dy1) || 1;
      var len2 = Math.sqrt(dx2*dx2 + dy2*dy2) || 1;
      var nx1 = dx1/len1, ny1 = dy1/len1;
      var nx2 = dx2/len2, ny2 = dy2/len2;
      var arcX1 = curr.x - nx1 * r;
      var arcY1 = curr.y - ny1 * r;
      var arcX2 = curr.x + nx2 * r;
      var arcY2 = curr.y + ny2 * r;
      parts.push('L' + arcX1 + ',' + arcY1);
      parts.push('Q' + curr.x + ',' + curr.y + ' ' + arcX2 + ',' + arcY2);
    }

    var last = points[points.length - 1];
    parts.push('L' + last.x + ',' + last.y);
    return parts.join(' ');
  }

  document.getElementById('nodeCount').textContent =
    rawData.nodes.length + ' nodes · ' + rawData.edges.length + ' edges';
})();
</script>
</body>
</html>
"""


def render_with_vis_html(
    nodes: list[DagNode], edges: list[DagEdge]
) -> str:
    """Build a self-contained HTML string using dagre.js for clean layout."""
    payload = {
        "nodes": [
            {"id": n.id, "label": n.label, "color": n.color, "title": n.title, "shape": n.shape}
            for n in nodes
        ],
        "edges": [
            {"source": e.source, "target": e.target}
            for e in edges
        ],
    }
    return _DAG_HTML.replace("__DATA__", json.dumps(payload))


def render_dag(snapshot: ProjectSnapshot) -> None:
    """Render the DAG inside a Streamlit app."""
    import streamlit as st

    nodes, edges = build_dag(snapshot)
    if not nodes:
        st.info("No models in this manifest to render.")
        return

    html = render_with_vis_html(nodes, edges)
    st.components.v1.html(html, height=750, scrolling=False)


__all__ = [
    "DagNode", "DagEdge", "build_dag", "render_dag",
    "render_with_vis_html", "HEALTHY", "SEMI_DOC", "SEMI_TEST",
    "UNHEALTHY", "SOURCE", "EXPOSURE", "_HEALTH_COLOR",
]