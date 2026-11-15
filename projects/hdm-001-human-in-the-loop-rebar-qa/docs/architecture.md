# Architecture

| Module | Responsibility |
|---|---|
| `src/rebar_qa/checks.py` | Pure functions. Takes row dictionaries, returns `Finding` objects. No file or database access, so it is easy to test. |
| `src/rebar_qa/workflow.py` | `triage` (routing and QA sampling), `Store` (SQLite: rows, findings, append-only decisions, metrics), `evaluate`, `render_report`. |
| `src/rebar_qa/generate.py` | Seeded synthetic BBS generator and ground truth. |
| `src/rebar_qa/cli.py` | Argument parsing, CSV reading and writing, input validation. |

## Data flow

1. `check` loads the CSV, validates the columns and row ids, runs `check_schedule`, then `triage`.
2. Rows, findings and routes are saved to SQLite and exported as `findings.csv` and `routing.csv`.
3. `queue` lists rows routed to `HUMAN_REVIEW` or `QA_SAMPLE` that have no decision yet.
4. `decide` and `import-decisions` append to the `decisions` table. A later decision on the same row overrides the earlier one in the metrics, but both stay stored.
5. `report` computes metrics from the three tables.

## Design decisions

- **Certain vs needs judgement** is set per rule, not learned. It is transparent and easy to explain; the false-alarm rate per rule shows where a threshold should move.
- **QA sampling of clean rows** is the only way to measure defects the rules cannot see. Without it the escape rate is unknown.
- **Standard library only**, so the project runs anywhere without setup.
- **Row id, not bar mark, is the key**, because duplicate bar marks are one of the defects being checked.
