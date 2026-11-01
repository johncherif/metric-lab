# Development log: design decisions and edge cases

Notes kept while building, for the milestone videos and the final report. Each entry says what happened, what changed,
and which course concept (if any) the change relates to.

## Data and content

| Finding | Change | Why it matters |
|---|---|---|
| Splitting "customers shown the offer" across the three products made no sense: the offer is not product-specific. | One row per week and segment; products are separate count columns (`plans_flex4`, ...). | Rates by product would otherwise use a meaningless denominator. |
| Averaging segment rates would give the wrong "All customers" rate. | Data stores **counts only**; every rate is recomputed from summed numerators and denominators. | Correctly weighted blends are essential for the Simpson's paradox scenario to be honest. |
| In Scenario 3, total card interest rose with the growing customer base and hid the cannibalization. | Show interest **per Flex Plan customer**. | The same denominator lesson the simulator teaches applied to building it. |
| Default rates for weeks 1 to 4 would show as 0%, but no first payments were due yet. | Rates with a zero denominator are blank, not zero; the chart note explains that payments start in week 5. | A 0% that means "no data" is itself a misleading metric. |
| A flat 0% charge-off line auto-scaled to an odd axis. | Charge-off and default charts share a fixed 0 to 7% scale. | Lets learners see "zero" next to a rising default rate on the same scale. |
| Content was authored grouped by role (all success metrics first). | Metrics and evidence are shown in a stable shuffled order. | Prevents learners from inferring answers from position (a validity threat to the assessment). |

## Scoring rules

| Edge case | Rule |
|---|---|
| One flag stretched across weeks 1 to 12 would "find" every trap on a chart. | At least half of a flag's weeks must fall inside the trap. |
| Several flags on the same issue. | Each issue is credited once; extra flags are shown as duplicates and are not counted as false alarms. |
| A later flag diagnoses an already-found issue differently. | Shown as a duplicate with the correct diagnosis, so the conflicting reasoning is visible. |
| A wrong diagnosis followed by a correct one on the same issue. | The correct flag wins; the earlier one becomes a duplicate. |
| A week range entered backwards (12 to 5). | Normalized before scoring. |
| One issue is visible on more than one chart (for example, the base change shows on the rate, impressions, and plan-count charts). | Traps list every chart where they can legitimately be seen. |
| Calibration with no flags, or only one. | No flags: "nothing to calibrate." One flag: the app declines to judge calibration from a single data point. |
| Learner submits with no flags. | Allowed, but only after confirming they found nothing worth flagging. |
| Stage 1 feedback reveals the correct answers. | Only the first attempt is scored; answers lock after checking. |
| Decision rationale left blank or one line. | Minimum 25 words, a recommendation, and at least one cited observation before submitting. |

## Interface (found in browser testing)

| Finding | Change |
|---|---|
| A range slider initialized only from session state collapsed to a single week. | Replaced with "From week" and "To week" selectors, which are also more keyboard-friendly. |
| A drag that started just past a marker (x = 5.1) dropped that week when only selected points were used. | Box edges round to the nearest week; selected points are the fallback. |
| The box selection stayed on the chart after a flag was added. | Charts are re-keyed after each flag, which clears the selection. |
| The locked rationale text box came back empty after submission. | The learner's rationale is shown as plain text beside the expert's. |

## Deployment (found on Streamlit Community Cloud)

| Finding | Change |
|---|---|
| Dollar amounts such as "$50 to $499.99" rendered as a math formula, because Streamlit markdown treats text between two "$" signs as LaTeX. Affected the products table, the Scenario 2 threshold explanation, and the Scenario 3 expert rationale. | All display text is escaped when content loads (Plotly legend labels are left raw, since Plotly is not markdown). A test now fails if an unescaped "$" reaches the interface. |
| The hidden `.streamlit/config.toml` was not uploaded, so the app ran in the viewer's dark theme with default red buttons; the hard-coded white chart background then clashed with the dark page. | Charts no longer hard-code colors and follow the Streamlit theme in light or dark mode. Config file still recommended for the intended look. |
| In a narrow window, Plotly chart titles were cut off and the legend overlapped the title. | Chart titles are rendered by Streamlit above each chart so they wrap; the legend sits just above the plot area. |
| The "Analyst: look here" label was nearly invisible on the light shading. | Label drawn in a darker amber that reads in both themes. |

## Live test of all three scenarios (Oct 31)

| Finding | Change |
|---|---|
| Escaping "$" for markdown also escaped Plotly number formats ("$,.0f"), so Scenario 3's dollar axes showed raw numbers. | Machine-read keys (number formats, ids, column names) are never escaped; a test compares formats with the source files. |
| Feedback read "This is a vanity or misleading." | Feedback uses short role nouns ("a vanity metric", "a guardrail"). |
| The review said confidence was "well matched" while the summary showed a 40% confidence gap. With confidence limited to 50-100% and outcomes of 0 or 1, the raw gap is large even for a calibrated learner. | Summary and results show one label computed with the same thresholds as the message. |
| The first hint pointed at an issue already found. | Hints target issues not yet found (support where it is needed). |
| Learners had to find the next scenario in the sidebar. | "Go to Scenario N" button on the summary. |
| A learner flagged every Scenario 2 issue, then chose "Ship" against those findings; another rated their own rationale 16/16 after a partly correct decision. | Open design items: show the learner's flags on the decision screen; compare self-ratings with auto-scored parts. |

## Known limitations (candidates for future work)

* **Flags are chart-level, not line-level.** On multi-line charts (default rate by product), a flag cannot specify which
  product's line the learner means. Credit is given for the right chart, weeks, and issue type.
* **Small-sample noise** in narrow segments (for example, near-prime Flex 4 Plus defaults) produces wiggles that
  learners may flag. This is realistic and is scored as a false alarm, but it may need a note in the briefing if
  testers find it unfair.
* **Progress lives in the browser tab.** Refreshing clears it; learners are told to download their log first.
* **Rationales are self-assessed.** Expert scoring of rationales happens in the evaluation, not in the app.
