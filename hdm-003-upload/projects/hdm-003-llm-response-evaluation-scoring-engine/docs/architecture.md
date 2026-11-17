# Architecture

```
run.py  (command line: generate, score)
  |
  |-- src/llm_eval/rubric.py     parse_rubric(), load_rubric()   -> Rubric, Criterion
  |-- src/llm_eval/loaders.py    load_cases(), load_responses(), load_human_scores()
  |-- src/llm_eval/checks.py     run_checks()      automated text checks for one response
  |-- src/llm_eval/scoring.py    score_response()  checks + ratings -> verdict, score, reasons, flags
  |                              score_all()       every response
  |-- src/llm_eval/compare.py    model_summary(), paired_comparison()
  |-- src/llm_eval/report.py     results.csv, summary.json, report.md
  `-- src/llm_eval/generate.py   synthetic sample data with ground truth
```

## Data flow

1. `rubric.py` reads the rubric and refuses to continue if it is inconsistent.
2. `loaders.py` reads test cases, responses and ratings. File-level problems stop the run. Row-level problems drop the row and add a line to the issue list shown in the report.
3. `scoring.py` handles one response at a time: it calls `checks.py`, averages the ratings per criterion, calculates the weighted score and applies the verdict rules.
4. `compare.py` groups results by model and, when there are exactly two models, compares them on shared cases.
5. `report.py` writes the same results in three forms: a table for spreadsheets, JSON for other programs, Markdown for people.

## Scoring rule

For each criterion: `normalised = (mean rating - scale_min) / (scale_max - scale_min)`.
Score = `100 x sum(weight x normalised)`. With a 1-5 scale, all 5s give 100 and all 1s give 0.

Verdict:

| Condition | Result |
|---|---|
| Forbidden phrase found, refusal missing, or refusal not needed | FAIL |
| Mean rating of a critical criterion below its `critical_min` | FAIL |
| Score below `pass_score` | FAIL |
| None of the above, all criteria rated | PASS |
| No automated failure, no ratings at all | NEEDS_HUMAN_SCORES |
| No automated failure, some criteria not rated | INCOMPLETE_SCORES |

A missing required fact and an over-long answer are warnings. They do not fail a response by themselves, because the human completeness and instruction-following ratings already cover them.

## Design choices

- **The rubric is data, not code.** Changing a weight or the pass mark needs no programming, and the file can be reviewed and versioned.
- **Critical failures are separate from the average.** An average hides single serious faults; a critical rule does not.
- **Missing ratings never become a pass.** The engine reports that a decision is not possible yet.
- **Human and automated signals are compared, not merged.** The automated checks do not change the human score. Where the two disagree, the response is flagged for a person to look at.
- **Every reason is kept.** A response that fails for three reasons shows all three, which makes failure counts useful.
- **Paired comparison.** Both models are compared on the same cases, which removes the effect of some cases being harder than others.
- **Fixed seeds.** The sample data and the bootstrap interval give the same numbers on every run.
- **Standard library only.** Nothing to install for the engine itself.
