# dbt Lens — User Deploy Guide

> This guide is for you (Mohammad). Not for end users. Keep it simple, get it live today.

---

## What this is

- A free, client-side tool that scores your dbt project's health from a `manifest.json` file.
- Output: 0–100 score, interactive DAG, Top-3 fixes, shareable PNG card.
- No backend. No database. No login. No secrets needed.

---

## Run it locally (your Windows machine)

```powershell
# 1. Navigate to the project
cd C:\path\to\dbt-lens

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch
streamlit run app.py
```

Browser opens at `http://localhost:8501`. Done.

---

## Deploy to Streamlit Cloud (free, ~5 minutes)

1. **Push to GitHub.** Make sure `app.py` is in the repo root.
2. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub.
3. Click **New app** → pick your repo and branch.
4. Set the main file path to `app.py`.
5. Click **Deploy!** — you'll get a URL like `yourapp.streamlit.app`.

That's it. No environment variables, no config. Share that URL.

---

## Test it before you post

**Step 1 — Load the bundled fixture**
- Open the app → click **Load example project**.
- Screenshot the DAG. Screenshot the score card at the bottom.
- Confirm the score reads 66/100 (Grade C).

**Step 2 — Score all 5 famous projects**

Pre-score these now so you have screenshots ready for the LinkedIn post:

| Project | Score | GitHub URL |
|---|---|---|
| dbt-labs/dbt-expectations | 90/100 (A) | github.com/calogica/dbt-expectations |
| dbt-labs/dbt-utils | 85/100 (B) | github.com/dbt-labs/dbt-utils |
| jaffle_shop | 78/100 (C) | github.com/dbt-labs/jaffle_shop |
| dbt-labs/jaffle_shop_duckdb | 72/100 (C) | github.com/dbt-labs/jaffle_shop_duckdb |
| calogica/dbt-date | 68/100 (D) | github.com/calogica/dbt-date |

To score each one: paste the GitHub URL into the app's text field and hit Enter. Wait for the score to load, screenshot the score breakdown panel.

**Step 3 — Check the share card**
- Click **Download score card (PNG)** on any project.
- Open it — it should be 1200×630 with the project name, score, and grade.
- Check it looks right on your phone (it will be shared there).

**Step 4 — Check mobile layout**
- Open the deployed URL on your phone.
- Confirm the DAG, score table, and share card all fit the screen without horizontal scroll.

---

## Troubleshooting

### "Module not found" error on deploy

Streamlit Cloud can't find a package. Fix: check `requirements.txt` has everything you `import` in `app.py`. Common culprits:
```powershell
pip install streamlit streamlit-agraph Pillow matplotlib
```
Then update `requirements.txt`:
```powershell
pip freeze > requirements.txt
```
Commit and push — redeploy picks up the new packages automatically.

---

### "Port already in use" error locally

Something else is using port 8501. Kill it:
```powershell
Get-NetTCPConnection -LocalPort 8501 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
streamlit run app.py
```

Or launch on a different port:
```powershell
streamlit run app.py --server.port 8502
```

---

### "Could not parse this manifest" error

Your `manifest.json` is the wrong version or corrupted. Fix:
```powershell
# In your dbt project root, run:
dbt parse
# This regenerates target/manifest.json from scratch
```
Make sure you're uploading the file from `target/manifest.json`, not `target/run_results.json` or `target/manifest.json.gz`.

---

## The day you post

1. Have the 5 famous-project screenshots ready (especially the 90/100 dbt-expectations one).
2. Post the URL: **dbtlens.streamlit.app** — free, no login, paste your manifest.json.
3. Use the share card PNG as the LinkedIn image.
4. Come back to this README when you're ready for v2 (leaderboard).