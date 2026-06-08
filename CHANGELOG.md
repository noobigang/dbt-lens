# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2025-06-08

### Added
- **Health Score** — 0–100 score across 6 weighted dimensions
- **Score Breakdown** — per-dimension earned/possible with actionable notes
- **Interactive DAG** — color-coded by health status (green/yellow/orange/red/blue/purple)
- **Compare to Famous Projects** — bar chart comparing your score vs. jaffle_shop, dbt-utils, dbt-expectations, etc.
- **Top 3 Fixes** — prioritized fixes with point recovery estimates
- **Share Card** — 1200×630 PNG generator
- **Client-side parsing** — manifest.json is parsed entirely in the browser, never uploaded
- **Bundle example project** — "Load example project" button so users can explore without uploading anything
- **GitHub URL loading** — paste any GitHub raw URL to a manifest.json and it fetches + parses it
- **Streamlit Cloud deployment** — zero config, free hosting