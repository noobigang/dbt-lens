# dbt Lens — Launch Kit

---

## Part 1: LinkedIn Launch Posts (3 Versions)

---

### Version A — "I built this" frame (Recommended)

Drop your `manifest.json` into most dbt repos and you get… nothing. No score. No DAG. No way to know if the project is a well-oiled machine or a tangled mess nobody has touched in a year.

So I built one.

**dbt Lens** — a free, client-side dbt project health auditor. Paste your `manifest.json` (free, no login, paste your manifest.json) and get:
- A 0–100 health score across 6 dimensions: test coverage (35%), documentation (20%), DAG structure (20%), naming (10%), exposures (10%), and materialization (5%)
- An interactive lineage DAG — color-coded so you can spot tested vs. untested models at a glance
- A Top-3 fix list — concrete, prioritized actions ranked by how many points they recover
- A shareable score card (1200×630, optimized for LinkedIn and Twitter)

I tested it on 5 famous dbt repos. The results were… eye-opening.

**[SCREENSHOT 1 — insert here: the DAG view of a famous project (e.g. dbt-labs/dbt-expectations, 90/100). Colorful nodes and edges, model names clearly visible, lineage flowing left to right. Place after "The results were… eye-opening."]**

**[SCREENSHOT 2 — insert here: the score breakdown panel showing all 6 dimension bars with earned/possible points and the final total score (90/100, Grade A). Place after Screenshot 1.]**

Try it: **dbtlens.streamlit.app** — free, no login, paste your manifest.json.

What does your dbt project score? Drop the number in the comments — I'm curious.

#dbt #dataengineering #analyticsengineering #opensource #buildinpublic

---

## Version B — "I audited 10 famous projects" frame

I ran a tool I built against 10 famous dbt repos. The average score was 23 out of 100.

Now — 23/100 isn't fair. Some of these projects are genuinely good. But even the best ones had the same blind spots: untested incremental models, columns with zero descriptions, lineage nobody had reviewed since onboarding. The problem isn't bad intent — it's that nobody has a way to see the whole picture at once.

So I built **dbt Lens** — a free, client-side auditor that takes a `manifest.json` and gives you:
- A 0–100 health score across 6 weighted dimensions
- An interactive lineage DAG (color-coded: green = tested & documented, red = neither)
- A Top-3 fix list, sorted by how many points each fix recovers
- A shareable 1200×630 score card ready to paste into a LinkedIn post

**[SCREENSHOT 1 — insert here: the comparison bar chart showing all 5 famous projects + the user's project highlighted in gold. Shows the full ranking. Place after "A shareable 1200×630 score card."]**

**[SCREENSHOT 2 — insert here: the 1200×630 share card PNG for dbt-expectations (90/100, Grade A). Clean design, project name, score, grade, tool URL. Place after Screenshot 1.]**

5 projects pre-scored so far. A public leaderboard is coming — submit yours and see where you rank.

Try it now — **dbtlens.streamlit.app** — free, no login, paste your manifest.json.

What does your dbt project score? Drop it below.

#dbt #dataengineering #analyticsengineering #toolbuild #buildinpublic

---

## Version C — "For recruiters" frame

You can see a candidate's GitHub. You can see their `dbt_project.yml`. But can you tell if their project is a well-engineered foundation — or a fragile mess held together by copy-pasted SQL from 2021? Because right now, you can't. Not really.

I built **dbt Lens** to solve exactly that. It's a free auditor that parses a `manifest.json` and scores a dbt project across 6 weighted dimensions: test coverage (35%), documentation (20%), DAG structure (20%), naming (10%), exposures (10%), and materialization (5%).

**[SCREENSHOT 1 — insert here: the score breakdown table with all 6 dimensions, each showing earned points / possible points + a progress bar. Place after "and materialization (5%)."]**

**[SCREENSHOT 2 — insert here: the interactive DAG. Color-coded nodes (green/yellow/orange/red), model names labeled, lineage arrows visible. Place after Screenshot 1.]**

The output is a single score (0–100), an interactive lineage view, Top-3 gaps, and a shareable PNG card. The candidate brings it to the interview. You see the score. No subjectivity, no guesswork.

Try it: **dbtlens.streamlit.app** — free, no login, paste your manifest.json.

Tag a recruiter who needs this.

#dbt #recruiting #dataengineering #analyticsengineering #techhiring

---

## v2: The Leaderboard

### How it works (submission → ranking)

1. **Google Form** — collects: project name, repo URL (required), Twitter/X handle (optional), email (optional, for notification).
2. **Google Sheets** — form submissions land here automatically.
3. **Daily automation** — a lightweight Python script runs each night: fetches `target/manifest.json` from each submitted repo URL, scores it with dbt Lens, and writes the score back to the sheet.
4. **Streamlit app refresh** — the "Hall of Fame" tab re-reads the sheet and updates the public leaderboard.

All free tools. No server. No budget.

### What gets collected

| Field | Required | Notes |
|---|---|---|
| Project name | Yes | Display name on leaderboard |
| Repo URL | Yes | Must be public, must contain `target/manifest.json` |
| Twitter/X handle | No | Used for the share card "shoutout" |
| Score | Computed | Auto-filled by automation, not by user |
| Submitted | Auto | Timestamp from form |

### Leaderboard UI ("Hall of Fame" tab)

A new tab in the Streamlit app, visible without uploading anything. Shows:
- Top 20 public projects ranked by score
- Columns: Rank, Project, Score, Grade, Repo link, Submitted date
- Click any row → opens the repo URL
- "Submit your project" button at the top → links to the Google Form

### The "Submit your project" button

On the main page, below the score card section: a prominent button that says **"Submit your project to the leaderboard →"** linking directly to the Google Form.

### The viral loop

1. User scores their project, downloads the share card.
2. They post it on LinkedIn/X: "My dbt project scored 84/100 — free tool: dbtlens.streamlit.app."
3. Their followers see a real score from a real project.
4. Some click through, try it, score their own.
5. Some submit to the leaderboard.
6. Loop.

The share card PNG includes the tool URL automatically — zero extra work for the sharer.

### Risks and fixes

**Risk: gaming**
- Someone modifies their `manifest.json` to inflate scores.
- *Fix:* scores are computed server-side by the automation script; the submitter never uploads a file, just a repo URL. The script fetches the real manifest.

**Risk: low-quality submissions (empty repos, broken links)**
- *Fix:* the automation checks if `target/manifest.json` actually exists in the repo before scoring. Skips and marks "manifest not found."

**Risk: anonymous or unverifiable submissions**
- *Fix:* repo URL is required and public — the project is verifiable. No anonymous entries.

**Risk: spam / duplicate submissions**
- *Fix:* Google Sheet has a deduplication rule on repo URL. Same repo scored twice = second submission silently ignored.