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

st.markdown("""
<style>
  /* Import Inter font */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  /* Global body */
  .stApp { font-family: 'Inter', -apple-system, sans-serif; }

  /* Hero section */
  .hero-wrap { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                border-radius: 16px; padding: 32px 36px; margin-bottom: 24px;
                border: 1px solid rgba(255,255,255,0.08); }

  /* Score metric styling */
  div[data-testid="stMetricValue"] { font-size: 2.8rem !important; font-weight: 800 !important; }

  /* Section headers */
  .st-emotion-cache-1v0fvj5 h2, .stMarkdown h2 { font-size: 1.25rem !important;
    font-weight: 700; color: #0f172a; border-bottom: 2px solid #d4af37;
    padding-bottom: 8px; margin-bottom: 16px; }

  /* Score table rows */
  .stDataFrame tbody tr:hover { background: #fef9ee !important; }

  /* Fix cards */
  [data-testid="stHorizontalBlock"] [data-testid="stBlock"] > div {
    border: 1px solid #e2e8f0 !important; border-radius: 12px !important; }

  /* Sidebar styling */
  section[data-testid="stSidebar"] { background: #f8fafc; }

  /* Download button */
  .stDownloadButton button { background: #d4af37 !important; color: white !important;
    font-weight: 700 !important; border: none !important; border-radius: 8px !important; }
  .stDownloadButton button:hover { background: #b8962e !important; }

  /* File uploader */
  .stFileUploader { border: 2px dashed #d4af37 !important; border-radius: 12px !important;
                    padding: 16px !important; background: #fef9ee !important; }

  /* Score grade badge coloring */
  [data-testid="stMetricDelta"] { font-size: 1.1rem !important; }

  /* Progress bars */
  .stProgress { border-radius: 8px; overflow: hidden; }

  /* Subheaders */
  h3 { color: #334155 !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)


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
    st.markdown("""
    <style>
    .hero-wrap {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-radius: 18px;
        padding: 36px 40px;
        margin-bottom: 28px;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 20px 60px rgba(0,0,0,0.15);
    }
    .hero-title { font-size: 2.4rem; font-weight: 900; color: #f8fafc;
                   line-height: 1.1; margin-bottom: 8px; }
    .hero-title span { color: #d4af37; }
    .hero-sub { color: #94a3b8; font-size: 1.05rem; margin-bottom: 28px;
                line-height: 1.6; }
    .hero-badge { display: inline-block; background: rgba(212,175,55,0.15);
                   border: 1px solid rgba(212,175,55,0.3); color: #d4af37;
                   font-size: 11px; font-weight: 700; padding: 3px 10px;
                   border-radius: 20px; letter-spacing: 0.5px; text-transform: uppercase;
                   margin-bottom: 12px; }
    .stButton>button {
        background: #d4af37 !important; color: white !important;
        font-weight: 700 !important; border: none !important;
        border-radius: 10px !important; font-size: 15px !important;
        padding: 0.5rem 1.5rem !important;
        box-shadow: 0 4px 14px rgba(212,175,55,0.4) !important;
    }
    .stButton>button:hover { background: #b8962e !important;
        box-shadow: 0 6px 20px rgba(212,175,55,0.5) !important; }
    .input-label { font-size: 12px; font-weight: 600; color: #64748b;
                   text-transform: uppercase; letter-spacing: 0.5px;
                   margin-bottom: 6px; display: block; }
    .stTextInput > div > div { border-radius: 10px !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="hero-wrap">
        <div class="hero-badge">Free · No Login · Instant Score</div>
        <div class="hero-title">🔬 <span>dbt Lens</span></div>
        <div class="hero-sub">
            Drop your <code>manifest.json</code> → get a 0–100 health score, interactive DAG,
            Top-3 fixes, and a shareable LinkedIn card.
            <br>Or paste a GitHub URL — any public dbt project works.
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 3, 1])
    with col1:
        st.markdown('<span class="input-label">📁 Upload manifest.json</span>', unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Drop your manifest.json here",
            type=["json"],
            help="The file dbt writes to target/manifest.json after `dbt parse` or `dbt build`.",
            key="manifest_uploader",
            label_visibility="collapsed",
        )
    with col2:
        st.markdown('<span class="input-label">🔗 GitHub URL</span>', unsafe_allow_html=True)
        url = st.text_input(
            "…or paste a public GitHub URL to target/manifest.json",
            placeholder="https://github.com/owner/repo/blob/main/target/manifest.json",
            key="manifest_url",
            label_visibility="collapsed",
        )
    with col3:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.markdown("&nbsp;", unsafe_allow_html=True)
        use_example = st.button("🎯 Load example", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

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
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 20px;
        border: 1px solid rgba(255,255,255,0.1);
        display: flex;
        align-items: center;
        gap: 40px;
    ">
        <div style="flex-shrink: 0;">
            <div style="font-size: 4rem; font-weight: 900; color: #d4af37; line-height: 1;">
                {score.total}<span style="font-size: 2rem; color: #64748b; font-weight: 400;">/100</span>
            </div>
            <div style="font-size: 1.4rem; font-weight: 700; color: #d4af37; margin-top: 4px;">
                Grade {score.grade}
            </div>
        </div>
        <div style="flex: 1;">
            <div style="font-size: 1.15rem; font-weight: 700; color: #f8fafc; margin-bottom: 8px;">
                {score.verdict}
            </div>
            <div style="font-size: 0.9rem; color: #94a3b8;">
                <span style="background: rgba(255,255,255,0.1); padding: 3px 10px; border-radius: 20px; margin-right: 8px;">
                    {score.model_count} models
                </span>
                <span style="background: rgba(255,255,255,0.1); padding: 3px 10px; border-radius: 20px; margin-right: 8px;">
                    {score.test_count} tests
                </span>
                <span style="background: rgba(255,255,255,0.1); padding: 3px 10px; border-radius: 20px; margin-right: 8px;">
                    {score.source_count} sources
                </span>
                <span style="background: rgba(212,175,55,0.2); padding: 3px 10px; border-radius: 20px; color: #d4af37;">
                    {score.exposure_count} exposures
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


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

    st.markdown("""
    <style>
    .comp-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
    .comp-title { font-size: 1.1rem; font-weight: 700; color: #0f172a; }
    .comp-rank { background: #d4af37; color: white; font-size: 12px; font-weight: 700;
                 padding: 4px 10px; border-radius: 20px; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(
        f'<div class="comp-header"><span class="comp-title">📊 Compare to famous dbt projects</span>'
        f'<span class="comp-rank">Your project: #{rank} of {len(rows)}</span></div>',
        unsafe_allow_html=True,
    )

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, max(3, 0.65 * len(rows))))
    fig.patch.set_facecolor("#f8fafc")

    names = [r[0] for r in rows]
    scores = [r[1] for r in rows]
    is_user = [r[2] for r in rows]
    bar_colors = []
    for u in is_user:
        if u:
            bar_colors.append("#d4af37")   # gold for user
        else:
            bar_colors.append("#94a3b8")   # slate for others

    bars = ax.barh(range(len(rows)), scores, color=bar_colors, height=0.6, edgecolor="white", linewidth=1.5)

    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(names, fontsize=12, fontweight="600", color="#0f172a")
    ax.invert_yaxis()
    ax.set_xlim(0, 105)
    ax.set_xlabel("Health Score (0–100)", fontsize=11, color="#64748b", labelpad=8)

    # Score labels on bars
    for i, (bar, sc, u) in enumerate(zip(bars, scores, is_user)):
        label = f"{sc}" + (" ★" if u else "")
        color = "#92400e" if u else "#475569"
        ax.text(sc + 1.5, i, label, va="center", fontsize=11, fontweight="700", color=color)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False, bottom=False)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0", "25", "50", "75", "100"], color="#94a3b8", fontsize=10)
    ax.grid(axis="x", color="#e2e8f0", linewidth=0.8, linestyle="--")
    ax.set_axisbelow(True)

    plt.tight_layout(pad=1.5)
    st.pyplot(fig, use_container_width=True)
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
