# Project explanation: HDM-001

## What Did We Build?

A command-line tool that reads a Bar Bending Schedule and sorts every row into one of four piles: accept automatically, send back to the detailer with a suggested fix, send to a human reviewer, or pick as a random spot check. It stores what the reviewer decided and then reports how good the automated checks were.

## Why Is This Project Important?

Any QA process has to decide what a machine can judge and what needs a person. If everything goes to people, it is slow and expensive. If everything is automated, wrong items slip through and nobody knows. A rebar checker has this problem, and so does an annotation or LLM-evaluation pipeline. QA leads, human data managers and checking engineers all need the same three things: a routing rule, an audit trail, and numbers that show whether the automation can be trusted.

## How Does It Work?

1. `check` reads the CSV and runs nine checks on each row.
2. Each finding is marked **certain** (arithmetic, fixed rule) or **needs judgement**.
3. Rows are routed: no findings = auto-accept; only certain errors = auto-flag; any judgement finding = human review.
4. 10 % of the auto-accepted rows are randomly pulled out as a QA sample for a human.
5. The reviewer records `issue` or `ok` for each queued row.
6. `report` calculates the automation rate, the false-alarm rate per rule and the escape rate.

Example: a 16 mm straight bar, 2 members x 5 bars, 4000 mm long.
- Total bars written as 12: certain error, auto-flagged, suggested value 10.
- Cut length written as 4050: only 50 mm off, could be an allowance, so it goes to a human.
- Cut length written as 4500: 500 mm off, certain error, auto-flagged.

## What Technologies Were Used?

- **Python standard library**: no installation needed, so anyone can run it.
- **csv**: schedules are commonly exchanged as tables; CSV is the simplest form.
- **sqlite3**: a single-file database, used for the decision log so history is never overwritten.
- **argparse**: gives the tool proper commands (`check`, `queue`, `decide`, `report`).
- **random with a seed**: makes the QA sample and the synthetic data reproducible.
- **pytest**: runs the 28 automated tests.

## What Did We Actually Implement?

Done:
- Nine checks, cut-length formulas for shape codes 00, 11, 21, 51
- Routing into four routes with seeded QA sampling
- Review queue, single and bulk decision recording, decision history
- Markdown and JSON reports with per-rule outcomes
- Synthetic data generator with ground truth, and an `evaluate` command

Not done (future): Excel import, more shape codes, two-reviewer agreement, adjustable thresholds, a web screen.

## What Were the Results?

- Sample run on 60 synthetic rows: 28 auto-accepted, 18 auto-flagged, 11 human review, 3 QA sample. 76.7 % of rows needed no human.
- Simulated reviewer: 5 of 11 human-review rows confirmed as issues, 6 cleared. 0 of 3 sampled clean rows had a defect.
- All 23 injected defect rows were caught and no clean row was auto-flagged.
- Tests: 28 executed, 28 passed.
- Limits on these numbers: the defects were injected by the same project that detects them, and the reviewer decisions were simulated from the ground truth. They show the workflow works, not how accurate it would be on a real schedule.
- Other limitations: four shape codes, illustrative thresholds, CSV only, one reviewer per row.
