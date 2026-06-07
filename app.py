"""dbt Lens — main Streamlit app.

Run with:

    streamlit run app.py

The app accepts a ``manifest.json`` via:
1. File upload
2. A public GitHub URL pointing at ``target/manifest.json``
3. A bundled example project (loaded from ``data/fixture_manifest.json``)
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from dbtlens import (
    card_generator,
    dag_renderer,
    famous_projects,
    parser,
    scorer,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
FIXTURE_PATH = ROOT / "data" / "fixture_manifest.json"
FAMOUS_PROJECTS_PATH = ROOT / "data" / "famous_projects.json"


# ---------------------------------------------------------------------------
# Page config & global style
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="dbt Lens — dbt Project Health Auditor",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Cached loaders
# ---------------------------------------------------------------------------


@st.cache_data
def load_fixture() -> bytes:
    """Return the bytes of the bundled fixture manifest."""
    return FIXTURE_PATH.read_bytes()


@st.cache_data
def load_famous_projects():
    """Return the configured famous projects, with JSON override support."""
    override = famous_projects.maybe_load_from_json(FAMOUS_PROJECTS_PATH)
    return override if override is not None else famous_projects.get_famous_projects()


def _render_hero_input() -> tuple[bytes | None, str | None]:
    """Render the three-input hero block; return (manifest_bytes, source_label)."""
    st.markdown(
        """
        <style>
        .hero-title { font-size: 2.6rem; font-weight: 800; color: #0f172a;
                       line-height: 1.1; margin-bottom: 0.25rem; }
        .hero-sub { color: #64748b; font-size: 1.05rem; margin-bottom: 1.5rem; }
        .stButton>button { font-weight: 600; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="hero-title">🔬 dbt Lens</div>', unsafe_allow_html=True
    )
    st.markdown(
        '<div class="hero-sub">Drop a <code>manifest.json</code> to audit '
        "your dbt project. Get a 0–100 health score, an interactive DAG, "
        "and a shareable card.</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([2, 3, 1])
    with col1:
        uploaded = st.file_uploader(
            "Drop your manifest.json here",
            type=["json"],
            help="The file dbt writes to target/manifest.json after `dbt parse` or `dbt build`.",
            key="manifest_uploader",
        )
    with col2:
        url = st.text_input(
            "…or paste a public GitHub URL to target/manifest.json",
            placeholder="https://github.com/owner/repo/blob/main/target/manifest.json",
            key="manifest_url",
        )
    with col3:
        st.write("")  # vertical alignment
        st.write("")
        use_example = st.button("Load example project", use_container_width=True)

    if uploaded is not None:
        return uploaded.getvalue(), f"uploaded file: {uploaded.name}"

    if use_example:
        return load_fixture(), "bundled example (fixture_manifest.json)"

    if url and url.strip():
        try:
            with st.spinner("Fetching manifest…"):
                snapshot = parser.parse_manifest_url(url.strip())
            # Re-serialize to bytes so the rest of the app uses one path.
            return (
                json.dumps(snapshot.raw_manifest).encode("utf-8"),
                f"URL: {url.strip()}",
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not load manifest from URL: {exc}")
            return None, None

    return None, None


def _render_sidebar() -> None:
    """Render the sidebar with 'About' and 'How scoring works' expanders."""
    with st.sidebar:
        st.markdown("### 🔬 dbt Lens")
        st.caption("v0.1.0 — A free dbt project health auditor.")
        st.markdown(
            "Paste a `manifest.json` to get a 0–100 health score, an "
            "interactive DAG, a Top-3 fix list, and a shareable image."
        )

        with st.expander("How scoring works", expanded=False):
            st.markdown(
                """
                Six weighted dimensions, summing to 100 points:

                | Dimension | Weight |
                |---|---|
                | Test coverage | 35 |
                | Documentation | 20 |
                | DAG structure | 20 |
                | Naming | 10 |
                | Exposures | 10 |
                | Materialization | 5 |

                **Test coverage** weights marts 2×, staging 1×,
                intermediate 0.5×. Incremental models with zero tests get
                a penalty. **Structure** rewards no orphans, no cycles,
                lineage ≤ 5 levels, and proper `stg_` / `fct_` /
                `dim_` naming. **Exposures** give 2 pts each.
                """
            )

        with st.expander("About", expanded=False):
            st.markdown(
                """
                dbt Lens is a **client-side** tool — your manifest is
                parsed in your browser session, never uploaded anywhere.

                Built with Streamlit. Source on GitHub.
                """
            )


def _render_score_header(score: scorer.HealthScore) -> None:
    """Render the score number, grade, and verdict line at the top."""
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.metric(
            label="Health score",
            value=f"{score.total}/100",
            delta=score.grade,
        )
    with c2:
        st.metric(label="Models", value=score.model_count)
    with c3:
        st.markdown(
            f"""
            **{score.verdict}**

            {score.source_count} sources · {score.test_count} tests ·
            {score.exposure_count} exposures
            """
        )


def _render_dimension_breakdown(score: scorer.HealthScore) -> None:
    """Render the dimension-by-dimension score table."""
    rows = []
    for d in score.dimensions:
        rows.append(
            {
                "Dimension": d.name,
                "Earned": round(d.earned, 1),
                "Possible": d.possible,
                "%": d.percent,
                "Notes": " · ".join(d.notes) if d.notes else "",
            }
        )
    df = pd.DataFrame(rows)
    st.subheader("Score breakdown")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "%": st.column_config.ProgressColumn(
                "%", format="%.0f", min_value=0, max_value=100
            ),
        },
    )


def _render_comparison(user_score: int, user_label: str) -> None:
    """Render the 'compare to famous projects' panel."""
    rows = famous_projects.rank_against(user_score, user_label=user_label)
    rank = famous_projects.user_rank(user_score)
    st.subheader("📊 Compare to famous projects")
    st.write(f"**Your project ranks #{rank} of {len(rows)}.**")

    # Use matplotlib for the bar chart (no extra deps beyond what we already pin)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, max(2.5, 0.55 * len(rows))))
    names = [r[0] for r in rows]
    scores = [r[1] for r in rows]
    is_user = [r[2] for r in rows]
    colors = ["#d4af37" if u else "#64748b" for u in is_user]
    bars = ax.barh(range(len(rows)), scores, color=colors, edgecolor="white")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(names)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Score (0–100)")
    for i, (bar, sc) in enumerate(zip(bars, scores)):
        ax.text(sc + 1, i, str(sc), va="center", fontsize=10, color="#0f172a")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def _render_fixes(score: scorer.HealthScore) -> None:
    """Render the 'Top 3 fixes' list."""
    st.subheader("🛠 Top fixes")
    if not score.fixes:
        st.success("No major gaps detected — your project is in good shape.")
        return
    for fix in score.fixes:
        with st.container(border=True):
            st.markdown(
                f"**#{fix.rank} — {fix.title}**  "
                f"<span style='color:#64748b'>(recover ~{fix.points_recoverable:g} pts, "
                f"dimension: {fix.dimension})</span>",
                unsafe_allow_html=True,
            )
            st.write(fix.explanation)


def _render_share_card(score: scorer.HealthScore) -> None:
    """Render the share-card preview + download button."""
    st.subheader("📤 Share your score")
    img = card_generator.generate_card(
        project_name=score.project_name,
        score=score.total,
        grade=score.grade,
    )
    st.image(img, caption="1200×630 — sized for LinkedIn and Twitter.", width=600)
    st.download_button(
        "⬇️ Download score card (PNG)",
        data=card_generator.card_to_bytes(img),
        file_name=f"dbt-lens-{score.project_name}-{score.total}.png",
        mime="image/png",
        use_container_width=False,
    )


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------


def main() -> None:
    _render_sidebar()

    manifest_bytes, source_label = _render_hero_input()
    if manifest_bytes is None:
        st.markdown("---")
        st.markdown(
            "👆 **Get started** by dropping a manifest, pasting a GitHub "
            "URL, or clicking *Load example project*."
        )
        st.markdown(
            "**Where do I find my manifest.json?** Run `dbt parse` or "
            "`dbt build` in your dbt project; the file lands at "
            "`target/manifest.json`."
        )
        return

    # Parse + score in a spinner
    try:
        with st.spinner("Analyzing your project…"):
            snapshot = parser.parse_manifest_bytes(manifest_bytes)
            score = scorer.score_project(snapshot)
    except Exception as exc:  # noqa: BLE001
        st.error(
            f"Could not parse this manifest. Is it a valid dbt "
            f"manifest.json? Detail: {exc}"
        )
        return

    # Stash in session state for the sidebar/refresh
    st.session_state["last_score"] = score
    st.session_state["snapshot"] = snapshot
    st.session_state["source_label"] = source_label

    st.success(f"Loaded {source_label}")

    # === The "wow moment" — DAG first, then the score.
    st.header("🕸  Project DAG")
    st.caption(
        "Green = tested & documented · Yellow = tests only · "
        "Orange = docs only · Red = neither · Blue = source · Purple = exposure"
    )
    dag_renderer.render_dag(snapshot)

    st.divider()

    st.header("📋  Health score")
    _render_score_header(score)
    _render_dimension_breakdown(score)

    st.divider()

    _render_comparison(score.total, score.project_name)

    st.divider()

    _render_fixes(score)

    st.divider()

    _render_share_card(score)

    # Footer
    st.markdown(
        "<div style='text-align:center; color:#94a3b8; padding: 2rem 0;'>"
        "Made with Streamlit · dbt Lens is a free, client-side tool. "
        "Your manifest is never uploaded to a server."
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
