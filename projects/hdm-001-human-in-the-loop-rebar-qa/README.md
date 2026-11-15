# HDM-001: Human-in-the-Loop Rebar QA System

A command-line tool that checks a Bar Bending Schedule (BBS), fixes nothing by itself, and decides for every row whether a machine can judge it or a person must. It keeps an audit trail of the human decisions and reports how well the automated checks performed.

> Prototype on **synthetic data**. It is not a code-compliance check and its output needs review by a competent engineer.

## Business problem

Checking a BBS by hand is slow, and checking it fully by script is risky: some errors are plain arithmetic, but others (a cut length that is 50 mm off, a bar longer than stock length) need judgement. The same problem appears in AI data operations: which items can be auto-accepted, which need a human reviewer, and how do you prove the automation is not letting defects through?

## Solution

1. Run rule-based checks on every row.
2. Label each finding **certain** (arithmetic or a fixed rule) or **needs judgement**.
3. Route each row:
   - `AUTO_ACCEPT`: no findings
   - `AUTO_FLAG`: only certain errors, returned to the detailer with a suggested value
   - `HUMAN_REVIEW`: at least one finding needs judgement
   - `QA_SAMPLE`: a random sample of clean rows, sent to a human as a spot check
4. Record reviewer decisions (`issue` or `ok`) in SQLite, append-only.
5. Report automation rate, false-alarm rate per rule, and escape rate from the QA sample.

## Features

- Nine checks: missing values, non-standard diameter, unit weight, total bars, total weight, cut length (gross error and small deviation), stock length, unsupported shape code, duplicate bar marks
- Simplified cut-length formulas for shape codes 00, 11, 21 and 51
- Seeded QA sampling of auto-accepted rows
- Review queue, single-decision and bulk-import commands, full decision history
- Markdown and JSON reports
- Synthetic BBS generator with known injected defects, and an `evaluate` command that compares routing with that ground truth

## Architecture

```
BBS CSV -> checks.py -> findings -> workflow.triage -> routes
                                        |
                                   SQLite store  <- human decisions (decide / import-decisions)
                                        |
                                 metrics -> report.md / report.json
```

See [docs/architecture.md](docs/architecture.md).

## Technology

Python 3.10+ standard library only (csv, sqlite3, argparse, random). pytest for tests.

## Install and run

```bash
pip install -r requirements.txt          # only needed for the tests

python run.py generate                                   # data/sample_bbs.csv + data/sample_truth.csv
python run.py check data/sample_bbs.csv --out-dir out    # findings.csv, routing.csv, qa.db
python run.py queue                                      # rows waiting for a human
python run.py decide --row 8 --reviewer datshin --decision issue --comment "bar is short"
python run.py report --out out/report.md
python run.py evaluate --truth data/sample_truth.csv     # only meaningful for synthetic data

python -m pytest
```

To replay the demonstration without typing decisions:

```bash
python run.py simulate-review --truth data/sample_truth.csv --out out/decisions.csv
python run.py import-decisions out/decisions.csv
```

## Example input

`data/sample_bbs.csv` (60 synthetic rows, seed 7):

```
row_id,bar_mark,member,shape_code,diameter_mm,a_mm,b_mm,c_mm,no_of_members,bars_per_member,total_bars,cut_length_mm,unit_weight_kg_m,total_weight_kg
```

`data/sample_truth.csv` records which rows were deliberately broken and how.

## Example output

From the committed run in `data/sample_output/`:

| Route | Rows |
|---|---:|
| Auto-accepted | 28 |
| Auto-flagged | 18 |
| Human review | 11 |
| QA sample | 3 |

- 76.7 % of rows needed no human.
- Of 11 human-review rows, the simulated reviewer confirmed 5 issues and cleared 6 (4 harmless length allowances, 2 valid but unsupported shapes).
- All 23 injected defect rows were caught; no clean row was auto-flagged.

These numbers describe this synthetic file only. The defects were injected by the same project that checks for them, so they say nothing about accuracy on real schedules. The reviewer decisions in `decisions_simulated.csv` are generated from the ground truth, not made by a person.

## Validation

28 automated tests cover the formulas, each check, routing, sampling, the decision log, metrics, generator reproducibility, four generator seeds end to end, and CLI error handling.

## Business applications

- First-pass QA of rebar schedules before issue
- A template for any review pipeline that mixes rules and people: annotation QA, LLM output review, document checks

## Skills demonstrated

Human-in-the-loop workflow design, quality sampling, audit trails, QA metrics (false-alarm rate, escape rate), rule-based data validation, synthetic test data with ground truth, Python, SQLite, pytest.

## Limitations

- Four shape codes only; formulas are simplified and ignore project-specific bending rules
- Thresholds (25 mm, 100 mm, 2 %) are illustrative, not from a standard
- Reads CSV only; real schedules arrive as Excel or CAD exports
- One reviewer per row; no second-reviewer agreement
- Each `check` run replaces the previous run in the database

## Future improvements

Excel import, more shape codes, reviewer agreement and adjudication, adjustable thresholds per project, a small web review screen.
