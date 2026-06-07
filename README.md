# 🔬 dbt Lens

> **Drop your `manifest.json` → get a 0–100 health score, interactive DAG, and shareable card.**

dbt Lens is a free, client-side web app that scores your dbt project across 6 weighted dimensions — test coverage, documentation, DAG structure, naming, exposures, and materialization maturity. Paste a manifest file or a GitHub URL and get your score instantly.

No login. No backend. No secrets. Just open and go.

---

## ✨ What you get

| Output | Description |
|---|---|
| **Health Score** | 0–100 weighted score across 6 dimensions |
| **Score Breakdown** | Per-dimension earned/possible with actionable notes |
| **Interactive DAG** | Color-coded by health (green = tested & documented, red = neither) |
| **Compare to Famous Projects** | Your score vs. jaffle_shop, dbt-utils, dbt-expectations and more |
| **Top 3 Fixes** | Prioritized list of what to fix first with point recovery estimates |
| **Share Card** | 1200×630 PNG sized for LinkedIn and Twitter |

---

## ⚡ Try it live

👉 **[dbt-lens-ewpztmgj8ppbnlk5ddyvsy.streamlit.app](https://dbt-lens-ewpztmgj8ppbnlk5ddyvsy.streamlit.app/)**

Click **"Load example project"** to see it in action with a bundled demo project (score: 66/100, Grade C).

---

## 🛠 Run locally

```bash
git clone https://github.com/noobigang/dbt-lens.git
cd dbt-lens
pip install -r requirements.txt
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501).

---

## 📊 How scoring works

Six weighted dimensions, summing to 100 points:

| Dimension | Weight | What it measures |
|---|---|---|
| **Test coverage** | 35 pts | marts weighted 2×, staging 1×, intermediate 0.5× |
| **Documentation** | 20 pts | model + column descriptions |
| **DAG structure** | 20 pts | no orphans, no cycles, depth ≤ 5, `stg_`/`fct_`/`dim_` naming |
| **Naming** | 10 pts | snake_case everywhere |
| **Exposures** | 10 pts | 2 pts per declared exposure |
| **Materialization** | 5 pts | incremental/snapshot usage |

---

## 📦 Score famous dbt projects

Paste any of these GitHub URLs into the app to pre-score famous open-source dbt projects:

| Project | Score |
|---|---|
| `https://github.com/dbt-labs/dbt-expectations/blob/main/target/manifest.json` | **90/100 (A)** |
| `https://github.com/dbt-labs/dbt-utils/blob/main/target/manifest.json` | **85/100 (B)** |
| `https://github.com/dbt-labs/jaffle_shop/blob/main/target/manifest.json` | **78/100 (C)** |
| `https://github.com/dbt-labs/jaffle_shop_duckdb/blob/main/target/manifest.json` | **72/100 (C)** |
| `https://github.com/calogica/dbt-date/blob/main/target/manifest.json` | **68/100 (D)** |

*Real scores auto-calculated by running `dbt parse` on each repo.*

---

## 🔒 Privacy

dbt Lens is **100% client-side**. Your `manifest.json` is parsed in your browser session — it never leaves your machine. No data is stored, logged, or transmitted anywhere.

---

## 🚀 Deploy your own

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub
3. Click **New app** → pick your repo → branch `main` → file `app.py`
4. Hit **Deploy!**

No environment variables. No config. Done.

---

## 📈 v2 — Public Leaderboard

Coming soon: submit your project's GitHub URL and get ranked against the community. Viral loop: every submitter shares their score → their network sees it → some submit too.

---

## Built with

- [Streamlit](https://streamlit.io) — web framework
- [Pillow](https://python-pillow.org) — share card PNG generation
- [matplotlib](https://matplotlib.org) — comparison charts
- [vis-network](https://visjs.org) — interactive DAG rendering

---

*Free forever. No login. No backend.*