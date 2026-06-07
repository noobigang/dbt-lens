# LinkedIn Post — dbt Lens Launch

## Version A — "I built this" (Recommended)

---

Drop your `manifest.json` into most dbt repos and you get… nothing.

No score. No DAG. No way to know if the project is a mess or a masterpiece.

So I built one.

**dbt Lens** — a free, client-side dbt project health auditor. Paste your `manifest.json` (free, no login, paste your manifest.json) and get:
- A 0–100 health score across 6 weighted dimensions (test coverage, documentation, DAG structure, naming, exposures, materialization)
- An interactive lineage DAG — color-coded by health (green = tested & documented, red = neither)
- A Top-3 fix list with point recovery estimates
- A shareable score card (1200×630, LinkedIn-ready)

I scored 5 famous open-source dbt repos with it. The results were… eye-opening.

**[SCREENSHOT 1 — the DAG view: dark slate background, colorful nodes with model names, legend panel on the right, zoom controls. Place after "The results were eye-opening."]**

**[SCREENSHOT 2 — the score breakdown: 66/100, Grade C, full dimension table with progress bars. Place after screenshot 1.]**

Try it: **https://dbt-lens-ewpztmgj8ppbnlk5ddyvsy.streamlit.app** — free, no login, paste your manifest.json.

What does your dbt project score? Drop it in the comments.

#dbt #dataengineering #analyticsengineering #opensource #buildinpublic

---

## Version B — "I scored 10 famous dbt projects" (Alternate)

---

I ran 10 famous dbt projects through a health auditor I built.

The average score: 23 out of 100.

Most weren't that bad — but even the good ones had gaps. Untested incremental models. Columns without descriptions. DAGs nobody had looked at in months.

So I built **dbt Lens** — a free, client-side auditor. Drop your `manifest.json`, get a 0–100 health score, an interactive DAG, and a shareable card.

**[SCREENSHOT 1 — comparison bar chart: your project in gold, famous projects in gray, score labels on bars]**

**[SCREENSHOT 2 — the share card: 1200×630, dark navy background, gold score "66/100", project name, URL in corner]**

5 famous projects pre-scored so far. More coming in a public leaderboard.

Try it now — **https://dbt-lens-ewpztmgj8ppbnlk5ddyvsy.streamlit.app** — free, no login, paste your manifest.json.

What does your dbt project score? Drop your number below.

#dbt #dataengineering #analyticsengineering #toolbuild #buildinpublic

---

## Version C — "For data engineers" (Alternate)

---

Most dbt projects I've seen have a problem:

Nobody knows how healthy they actually are.

There's no score. No DAG you can show a stakeholder. No way to compare your project to anyone else's.

Until now.

I built **dbt Lens** — a free, client-side dbt project health auditor. Paste your `manifest.json` and get a 0–100 score across 6 dimensions, an interactive lineage DAG, and a shareable card.

**[SCREENSHOT — the DAG: colorful nodes, dark background, professional look]**

**[SCREENSHOT — the score: 66/100, Grade C, breakdown table]**

It's free. No login. No backend. Your manifest never leaves your browser.

Try it: **https://dbt-lens-ewpztmgj8ppbnlk5ddyvsy.streamlit.app**

If you try it — drop your score in the comments. Curious what the community looks like.

#dbt #dataengineering #analyticsengineering #buildinpublic #data