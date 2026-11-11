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

## Iteration after the Milestone 1 critique (Nov 1)

Aligned with the submitted proposal: the fictional bank is **JT Morgan** and the product family is **JT FlexBuy**
(FlexBuy, FlexBuy Plus with a 4.5% fee, FlexBuy Plan with a fixed interest rate). The start page frames adoption,
engagement, and value as a flywheel and states the growth-mindset premise of the proposal.

| Critique or source | Change | Course concept |
|---|---|---|
| The Apply outcome was never practiced: learners only sorted ready-made metrics | "Define it" step: build a metric from numerator, denominator, and time window, with feedback on each part, and name a guardrail | Constructive alignment (Biggs) |
| Scenario 1 walkthrough answers counted as detections | Flags on walkthrough issues are tagged "guided" and reported separately from issues found independently | Measurement validity |
| "Something is always wrong" cue | Scenario 1 adds a clean complaints chart with nothing planted; every briefing says some charts are fine | Validity; desirable difficulty |
| Confidence slider defaulted to 70%, and overlooked issues never counted | Confidence is an active choice for every flag (no default); a required "did you find every issue?" rating is compared with issues found | Metacognition: calibration |
| Self-rating 16/16 after a partly correct decision went unremarked | Summary compares the rubric self-rating with the auto-scored decision and evidence | Calibration of self-assessment |
| A learner flagged every issue, then decided against those findings | Decision screen opens with "What the dashboard showed" | Constructive alignment; Sadler |
| Feedback was mostly task-level | Review adds a process checklist and a growth-mindset note | Hattie & Timperley (process level); attribution theory |
| Add-these: productive failure | Each scenario opens with a committed first impression; the summary contrasts it with the expert view | Productive failure (Kapur) |
| Add-these: help-seeking | Hints unlock after a first flag or two minutes; hint timing is logged | Help-seeking research |
| Add-these: SOLO rubric (also Varun's peer review) | Rubric levels explained as SOLO levels; one example rationale per level for each scenario | SOLO taxonomy; Sadler (exemplars) |
| Add-these: expectancy-value | "Why this matters" in every briefing; early success via the worked example | Expectancy-value theory |
| Gagné's events | Learning objectives at the top of each briefing; a recall check opens Scenarios 2 and 3 (interleaving Scenario 1 and 2 content) | Gagné; testing effect; interleaving |
| Accessibility | Text description for each chart and a "View as a table" option; glossary in the sidebar and start page | UDL; Mayer's pre-training principle |
| Yanze's peer review: time on task | Time in every stage is logged and summarized | Controlled experiments: threats to validity |
| Akilan's peer review: real tools | "Download this scenario's data (CSV)" for exploring in Excel, Tableau, or Power BI | Authenticity, without added cognitive load |
| Tester feedback (two non-analyst testers): interesting but difficult | Glossary, objectives, and process checklist reduce the vocabulary barrier; testers sit outside the target audience of analysts and PMs | Rosenshine (~80% success in guided practice); audience fit |

## Iteration after Milestone 1 peer feedback (Nov 10)

| Feedback (source) | Change | Course concept |
|---|---|---|
| Confidence asked too often (John; Shivani: "keep it, but use it") | Per-flag confidence removed. One question per scenario ("how sure are you that you found every issue?"). "My results" turns those ratings into a pattern by concept: issues missed while 80% or more sure are listed as blind spots, each linked to the lesson that teaches it | Calibration and metacognitive monitoring; feedback that closes the gap (Sadler) |
| Hard for outsiders; "ELI5 some sections" (Livia); "a curriculum that walks through the concepts" (Shivani); both testers | New "Learn the basics" primer: seven plain-language lessons, each with a one-sentence idea, an everyday analogy, the JT FlexBuy example, a small chart, and a quick check. Every issue type maps to a lesson, and missed issues link back to it | Mayer's pre-training principle; worked examples; UDL (multiple means of representation) |
| Each briefing memo assumes analytics vocabulary | "In plain words" summary at the top of every briefing | Coherence and signaling (Mayer); UDL |
| Scenario 1 felt long; cut the sort to about six (Xuanzhe) | Six metrics per scenario instead of twelve, all three roles represented, mixed counts per role so elimination does not give answers away | Cognitive load (extraneous load) |
| "Need a hint?" before submitting (Xuanzhe); do not hold hints back, frame the delay as productive failure (grader) | Hint button available from the start; a short note invites a first look on your own. Time and flags before each hint are still logged | Productive failure (Kapur); help-seeking |
| Assessment felt like a language-test writing task (Livia) | Plain-language meaning of ship, iterate, and roll back; "Fill in sentence starters" button; minimum length lowered from 25 to 15 words; bracketed starters must be replaced before submitting | Scaffolding; UDL (multiple means of expression) |
| Keep the self-assessment but make it one quick rating after the comparison (Xuanzhe) | One holistic rating (four plain SOLO levels) right below the side-by-side comparison, replacing four criteria. The check against the auto-scored parts is unchanged | SOLO taxonomy; calibration of self-assessment |
| Get at least one analyst or PM before the next milestone (grader) | Open: recruit analyst and PM testers for the next round | Audience fit |

Found while testing this iteration: the primer's progress bar was drawn before a quick check was recorded, so it read "0 of 7" after a correct answer. It is now drawn after the lessons.

## Known limitations (candidates for future work)

* **Flags are chart-level, not line-level.** On multi-line charts (default rate by product), a flag cannot specify which
  product's line the learner means. Credit is given for the right chart, weeks, and issue type.
* **Small-sample noise** in narrow segments (for example, near-prime Flex 4 Plus defaults) produces wiggles that
  learners may flag. This is realistic and is scored as a false alarm, but it may need a note in the briefing if
  testers find it unfair.
* **Progress lives in the browser tab.** Refreshing clears it; learners are told to download their log first.
* **The single confidence rating is per scenario, not per concept.** The blind-spot pattern infers concepts from what was missed; a learner who is sure about one issue but unsure about another cannot say so.
* **Rationales are self-assessed.** Expert scoring of rationales happens in the evaluation, not in the app.
