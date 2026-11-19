# Architecture: HDM-004 Automated BBS Validator

## Specification

| Item | Detail |
|---|---|
| Title | Automated Bar Bending Schedule Validator |
| Problem | Schedules are checked by hand, unevenly, and whole-schedule rules are easy to miss |
| Users | Rebar detailers, checking engineers, detailing team leads; more generally anyone who gates batches of human-produced records |
| Features | 22 rules, rule profile as JSON, CSV and XLSX input, batch run, PASS / REVIEW / FAIL verdict, release exit code, CSV / JSON / HTML reports |
| Stack | Python standard library, openpyxl, pytest |
| Inputs | Schedule files, optional title block and weight summary, rule profile |
| Outputs | `findings.csv`, `summary.json`, `report.html`, console table, exit code |
| Success criteria | Every planted defect found with the right rule; no finding on correct rows; unreadable input reported, never a crash |
| Validation | 77 tests, including an exact match against planted ground truth |
| Limitations | Illustrative profile, ten shape codes, one input layout, synthetic data only |

## Modules

| File | Responsibility |
|---|---|
| `src/bbs_validator/profile.py` | Loads and validates the rule profile. Parses shape formulas and constraints into a checked syntax tree and evaluates them. |
| `src/bbs_validator/loaders.py` | Reads CSV (+ `.meta.json`) or XLSX into a `Schedule` object. Finds schedule files in a folder. |
| `src/bbs_validator/rules.py` | The rule catalogue `RULES`, row checks, schedule checks, weight calculation and the verdict. |
| `src/bbs_validator/engine.py` | Runs the rules over one file or a folder. Turns results into an exit code. |
| `src/bbs_validator/report.py` | Builds the summary and writes the three output files. |
| `src/bbs_validator/generate.py` | Builds the synthetic sample data and the list of planted defects. |
| `run.py` | Command line: `generate`, `validate`, `shapes`, `rules`. |

## Data flow

1. `load_profile` reads the JSON profile. Every formula is parsed once. If anything is wrong, one `ProfileError` lists all problems and nothing is validated.
2. `find_schedules` lists the `.csv` and `.xlsx` files.
3. `load_schedule` turns each file into a `Schedule`: a list of row dictionaries (each with its line number in the file), an optional header and an optional weight summary. A file that cannot be read raises `ScheduleError`, which the engine turns into an UNREADABLE result.
4. `check_schedule` runs `check_row` on every row and then the schedule-level checks. Each problem becomes a `Finding` with schedule, line, bar mark, rule, severity, message and suggested value.
5. `verdict` reduces the findings to PASS, REVIEW or FAIL.
6. `write_outputs` writes the files. `exit_code` gives 0 or 1.

## Design decisions

**Rules as data.** The numbers that change between standards and projects are in the profile. Adding a shape code means adding one JSON entry with its dimensions, formula, end legs and optional constraints. No code change is needed.

**Safe formulas.** A formula is text from a file, so it must not be run with Python's `eval`. `parse_formula` uses the `ast` module to read the expression and accepts only numbers, the names `A`-`E`, `d`, `r`, the four arithmetic operators and brackets. A function call, attribute access or any other name is rejected when the profile is loaded. The test suite includes an attempt to import a module through a formula.

**Stop checks that depend on a failed check.** If a diameter is not in the profile, the bend radius is unknown, so the cut length is not recalculated for that row. If a needed dimension is missing, the geometry checks are skipped. This avoids several misleading findings for one root cause. The end-to-end test, which allows no extra findings, enforces this.

**Two severities.** An error is something that is wrong whatever the intent, such as arithmetic. A warning is something a person must judge, such as a bar longer than 12 m, which may be a real special delivery. The verdict keeps the two apart, and `--strict` lets a team choose to block on warnings too.

**Reconcile, do not recalculate silently.** The weight summary check compares what the schedule declares with what its own rows add up to. If a bar size has a row with unusable values, that size is not reconciled and a note says so. The tool does not guess.

**Batch isolation.** One unreadable file must not hide the results for the others, so it becomes a result with verdict UNREADABLE and still makes the exit code 1.

**Repeatable outputs.** Reports contain no timestamps, so the same input gives the same files and they can be compared between runs.

## Cut length rule

For a row with shape code `s`, bar size `d` and dimensions from the row:

```
r        = minimum former radius for d (from the profile)
raw      = formula of s evaluated with A-E, d, r
expected = raw rounded up to the next multiple of length_rounding_mm
error if |scheduled - expected| > cut_length_tolerance_mm
```

Example: shape 11, d = 16, r = 32, A = 1800, B = 400. raw = 1800 + 400 - 16 - 16 = 2168. expected = 2175. A scheduled length of 2175 or 2200 is accepted with the default tolerance of 25 mm. 2225 is an error with suggested value 2175.
