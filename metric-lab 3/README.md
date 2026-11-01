# Metric Lab: BNPL Launch Review

A scenario-based simulator for CS6460 (Educational Technology). Learners play an analyst at a fictional bank
reviewing the launch of a buy now, pay later feature, and practice measuring a digital feature across
**adoption, engagement, and value**. Harborline Bank, its products, and all data are fictional.

Each scenario has three stages:

1. **Choose metrics:** sort 12 candidate metrics into success, guardrail, or vanity, with explained feedback.
2. **Read the dashboard:** flag misleading patterns in synthetic launch data, name the issue type, and rate confidence.
3. **Decide and justify:** recommend ship, iterate, or roll back, cite evidence, write a rationale, compare it with an
   expert's, and self-assess against a four-criterion rubric.

Support fades: Scenario 1 is a worked example, Scenario 2 offers hints on request, Scenario 3 offers none.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
streamlit run streamlit_app.py
```

## Tests

```bash
python -m pytest -q
```

The suite covers the scoring rules and their edge cases, confirms that the generator really plants each trap its
answer key describes, checks that every content file is internally consistent, and plays every scenario end to end
with Streamlit's `AppTest` harness.

## Change the data or content

* **Data and answer keys:** edit `generator/generate.py`, then run `python -m generator.generate`. Each scenario's data
  (`data/scenarioN_data.csv`) and answer key (`data/scenarioN_key.json`) are written together from one seeded function,
  so they cannot drift apart.
* **Scenario text, metrics, charts, decisions:** edit `content/scenarioN.json`. Shared labels and the rubric are in
  `content/common.json`. Run the tests afterwards; they catch broken references between content and answer keys.

## Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repository (public, or private with Streamlit's GitHub access granted).
2. Sign in at Streamlit Community Cloud with GitHub and create a new app from the repository.
3. Set the main file to `streamlit_app.py` and choose a Python version that matches your local one (built on 3.13).
4. Open the app link in an incognito window to confirm it loads without signing in.

The free tier puts apps to sleep after a period without traffic. The first visit after that takes about a minute to
wake the app; reviewers should be warned in the Instructions document.

## Project layout

```
streamlit_app.py        Streamlit UI: navigation and the three stages
metric_lab/scoring.py   Pure scoring functions (metric sorting, flags, calibration, decision)
metric_lab/charts.py    Plotly figures and chart-selection handling
metric_lab/content.py   Loads content, data, and answer keys; computes chart series
metric_lab/logger.py    In-session event log and CSV export
generator/generate.py   Seeded synthetic data and answer keys for all scenarios
content/                Scenario content (JSON) and shared labels/rubric
data/                   Generated data and answer keys (committed so the app needs no build step)
tests/                  Unit, generator, content-integrity, and end-to-end tests
DEVLOG.md               Design decisions and edge cases found while building
```

## Privacy

No login and no personal data. Learner actions are kept only in the browser session and can be downloaded as a CSV
by the learner. Closing or refreshing the tab clears progress.
