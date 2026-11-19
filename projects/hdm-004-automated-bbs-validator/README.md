# HDM-004: Automated Bar Bending Schedule Validator

A command-line tool that checks Bar Bending Schedules (BBS) before they are issued. It reads a folder of schedules in CSV or Excel format, applies 22 rules, gives each schedule a verdict of PASS, REVIEW or FAIL, and writes a findings list, a JSON summary and an HTML report.

All schedules in this folder are synthetic. The tool is a prototype: its checks are not an engineering approval and not a code-compliance check. See [Limitations](#limitations).

## Business problem

A bar bending schedule tells the fabricator how many bars to cut, how long, and how to bend them. Mistakes in it become wrong steel on site. Manual checking is slow and uneven:

- A checker recalculates cut lengths by hand for some rows, not all.
- Rules that look at the whole schedule are easy to skip: a bar mark used twice, a weight summary that no longer matches the rows after a late edit, an empty revision box.
- Each detailing office keeps its limits (bar sizes, bend radii, rounding) in people's heads or inside spreadsheet formulas, so they are hard to review or change.
- There is no simple gate that says "this batch may be issued" or "this batch may not".

The same problem appears in any data operation: records arrive from people, and something must decide which batches are fit to release and explain why.

## Solution

1. **Rule profile as data.** Bar sizes, minimum bend radii, minimum end projections, rounding, tolerances and the cut-length formula for each shape code live in one JSON file. Formulas are plain text such as `A + B - 0.5*r - d`.
2. **Row checks.** Every row is checked for empty or invalid cells, quantity arithmetic, dimensions the shape needs, bend geometry, and the cut length recalculated from the shape code.
3. **Schedule checks.** Duplicate bar marks, required title-block fields, and the declared weight summary reconciled against the rows per bar size.
4. **Verdict.** Any error gives FAIL. Only warnings gives REVIEW. No findings gives PASS.
5. **Release gate.** The exit code tells a script or CI job whether the batch may go out.

How this differs from project 001: that project decides which rows go to a human reviewer and records the reviewer's decisions. This project is the validation engine itself, with ten shape codes kept as data, schedule-level reconciliation, Excel input, batch runs and a release gate.

## Features

- CSV and XLSX input; both become the same internal object
- Ten shape codes (00, 11, 13, 21, 31, 33, 41, 44, 51, 63) defined in the profile, not in code
- Safe formula evaluator: a profile can contain only numbers, `A`-`E`, `d`, `r` and `+ - * /`; anything else is rejected when the profile loads
- 16 error rules and 6 warning rules, each with a plain-English message and, where possible, a suggested value
- Weight summary reconciliation per bar size with a percentage tolerance
- Batch mode: a file that cannot be read is reported as UNREADABLE and the other files are still checked
- `--strict` option that makes warnings block release
- Outputs: `findings.csv`, `summary.json`, `report.html` (one self-contained file)
- Profile validation that lists every problem in one message

## Rules

| Severity | Rule | Meaning |
|---|---|---|
| error | `missing_value` | A required cell is empty |
| error | `invalid_number` | A numeric cell does not hold a number |
| error | `invalid_quantity` | A quantity is not a whole number above zero |
| error | `non_standard_diameter` | Bar size is not in the profile |
| error | `total_bars_mismatch` | Total bars is not members x bars per member |
| error | `missing_dimension` | The shape needs a dimension that is empty |
| error | `invalid_dimension` | A dimension is not a number above zero |
| error | `shape_constraint_failed` | Dimensions cannot form the shape |
| error | `leg_too_short` | An end leg is shorter than the minimum end projection |
| error | `cut_length_mismatch` | Cut length differs from the shape-code calculation |
| error | `duplicate_bar_mark` | A bar mark is used on more than one row |
| error | `empty_schedule` | The schedule has no bar rows |
| error | `header_missing` | A required title-block field is empty or absent |
| error | `summary_weight_mismatch` | Declared weight differs from the weight of the rows |
| error | `summary_diameter_missing` | A bar size in the rows is absent from the weight summary |
| error | `summary_diameter_unexpected` | The weight summary lists a bar size that has no rows |
| warning | `unknown_shape_code` | Shape code is not in the profile, so it cannot be checked |
| warning | `unused_dimension` | A dimension is filled in that the shape does not use |
| warning | `cut_length_not_rounded` | Cut length is not a multiple of the rounding step |
| warning | `exceeds_max_length` | Cut length is longer than the maximum bar length |
| warning | `bar_mark_format` | Bar mark does not match the expected format |
| warning | `no_weight_summary` | No weight summary was supplied, so totals were not reconciled |

## Architecture

```
profile_bs8666_style.json        schedules/*.csv (+ .meta.json)   schedules/*.xlsx
          |                                   \                      /
     profile.py  (validate, safe formulas)          loaders.py  -> Schedule
          \_______________________________________________/
                                  |
                              rules.py   (row checks, schedule checks, verdict)
                                  |
                              engine.py  (batch run, exit code)
                                  |
                              report.py  -> findings.csv, summary.json, report.html
```

More detail in [docs/architecture.md](docs/architecture.md). A plain-English walk-through is in [docs/project_explanation.md](docs/project_explanation.md).

## Technology

- Python 3.10+ standard library (`ast`, `csv`, `json`, `argparse`, `dataclasses`, `html`)
- openpyxl, only for reading and writing `.xlsx`
- pytest for the tests

No pandas: the rules work row by row and schedules are small, so plain Python keeps the tool easy to install and read.

## Install and run

```bash
pip install -r requirements.txt
python run.py validate data/schedules --out-dir out    # check the sample folder
python run.py validate data/schedules/S-101_footings_rev_B.csv --out-dir out
python run.py validate data/schedules/S-205_columns_rev_A.csv --strict
python run.py shapes                                   # shape codes and formulas
python run.py rules                                    # all rules
python run.py generate                                 # rebuild the sample data
python -m pytest -q                                    # run the tests
```

Use another profile with `python run.py --profile my_profile.json validate ...`.

Exit codes: `0` no schedule blocks release, `1` at least one schedule is FAIL or UNREADABLE (or REVIEW with `--strict`), `2` the command could not run (path or profile problem).

## Input

Schedule columns (header names are matched without regard to case or spaces):

| Column | Required | Content |
|---|---|---|
| `bar_mark`, `member` | yes | Text |
| `diameter_mm` | yes | Bar size |
| `no_of_members`, `bars_per_member`, `total_bars` | yes | Whole numbers |
| `shape_code` | yes | For example `00`, `11`, `51` |
| `a_mm` | yes | Dimension A |
| `b_mm` to `e_mm` | when the shape needs them | Dimensions B to E |
| `cut_length_mm` | yes | Scheduled cut length |

Title block and weight summary:

- CSV: a file with the same name ending in `.meta.json`, holding `header` (field and value) and `weight_summary` (a list of `diameter_mm` and `total_weight_kg`).
- XLSX: sheets named `Schedule`, `Header` (columns field, value) and `Summary` (columns diameter_mm, total_weight_kg).

## Sample data

Created by `src/bbs_validator/generate.py` with a fixed seed. Clean rows are calculated from the profile, so they are correct by construction. Defects are then planted one at a time and listed in `data/planted_defects.csv`.

| File | Content | Expected |
|---|---|---|
| `S-101_footings_rev_B.csv` | 14 correct rows, full title block, matching weights | PASS |
| `S-205_columns_rev_A.csv` | 12 rows with 5 planted warnings | REVIEW |
| `S-310_beams_rev_C.csv` | 16 rows with 11 planted row errors | FAIL |
| `S-402_slab_rev_A.xlsx` | 7 rows, 1 cut-length error, 2 empty title-block fields, 3 weight-summary errors | FAIL |
| `S-518_walls_rev_A.csv` | 10 correct rows, no title block and no weight summary | FAIL |
| `invalid/missing_columns.csv` | Four required columns absent | UNREADABLE |
| `invalid/headers_only.csv` | Column headers and no rows | FAIL |
| `invalid/profile_invalid.json` | Profile with three faults, one of them an attempt to run code | rejected |

The CSV and JSON samples are rebuilt byte for byte by `generate`. The `.xlsx` file is rebuilt with the same cell values, but the file bytes change because Excel files store a save time.

## Example output

Console output for the sample folder (synthetic data):

```
Schedule                  Verdict     Rows  Errors  Warnings
S-101_footings_rev_B.csv  PASS          14       0         0
S-205_columns_rev_A.csv   REVIEW        12       0         5
S-310_beams_rev_C.csv     FAIL          16      11         0
S-402_slab_rev_A.xlsx     FAIL           7       6         0
S-518_walls_rev_A.csv     FAIL          10       6         1

5 schedule(s), 59 bar rows, 23 error(s), 6 warning(s).
```

Rows from `data/sample_output/findings.csv`:

| Schedule | Line | Mark | Rule | Message | Suggested |
|---|---:|---|---|---|---|
| S-310_beams_rev_C.csv | 3 | 02 | cut_length_mismatch | Cut length 3400 mm, shape 21 gives A + B + C - r - 2*d = 3090, rounded up to 3100 mm | 3100 |
| S-310_beams_rev_C.csv | 7 | 06 | leg_too_short | Leg B = 150 mm is below the minimum end projection 240 mm for a 25 mm bar | |
| S-402_slab_rev_A.xlsx | | | summary_weight_mismatch | 12 mm bars: summary declares 885.8 kg, rows give 962.8 kg (8.0% apart) | 962.8 |

The broken profile is rejected with every fault in one message:

```
ERROR: invalid profile: 'length_rounding_mm' must be a number greater than 0; shape '11': formula uses B which is not in 'dimensions'; shape '21': formula '__import__('os').getcwd()' uses something that is not allowed (only numbers, A, B, C, D, E, d, r and + - * / are accepted)
```

## Validation

- 77 automated tests, all passing (`python -m pytest -q`).
- Each of the ten shape formulas is tested against a number worked out by hand, separately from the sample-data generator.
- Boundary tests: cut-length tolerance (25 mm accepted, 50 mm rejected), minimum end projection (240 mm accepted, 235 mm rejected), weight tolerance (0.5% accepted, 4.9% rejected).
- End-to-end test on the sample folder: the findings must equal the 29 planted defects exactly, by schedule, line, bar mark and rule. A missed defect or an extra finding fails the test.
- Every one of the 22 rules is triggered at least once by the sample data.
- Loader tests: CSV and XLSX give identical rows; unreadable files give a clear message.
- The HTML report was opened once in a headless browser and looked at. There are no automated tests of how it looks.

What this does and does not prove: the tool applies its rules correctly to data built for it and finds every planted defect without false alarms on that data. It does not show how the tool behaves on real schedules, which have many layouts, more shape codes and project-specific rules. The formulas and limits in the profile are illustrative and were not checked against a purchased copy of any standard.

## Business applications

- A pre-issue gate for a detailing team: only PASS schedules go to the checker for engineering review
- First-pass checking of schedules received from a subcontractor
- A repeatable way to measure which defect types are most common in a batch
- The same pattern (rules as data, severity levels, batch verdict, release gate) applies to checking annotation batches or evaluation datasets before delivery

## Skills demonstrated

Data validation rule design, severity levels and release gating, configuration-driven rules, safe expression evaluation, reconciliation of declared totals against detail records, multi-format data loading (CSV, XLSX), batch processing with error isolation, synthetic test data with planted defects and ground truth, structured reporting (CSV, JSON, HTML), Python CLI, pytest.

## Limitations

- Prototype only. A PASS means the schedule passed these automated checks. It does not mean the reinforcement design or detailing is correct or approved.
- The profile is a BS 8666-style illustration with ten shape codes. Formulas, bend radii and end projections must be verified against the standard and the project specification before any real use.
- Shape codes that are not in the profile are flagged and not checked.
- No check against drawings: the tool cannot know whether the right bar is scheduled, only whether the schedule is consistent with itself.
- Only one schedule layout is read. Real schedules exported from detailing software would need a column mapping step.
- Dimension D of the bar and the bar diameter both use the letter d in different cases (`D` and `d`) in formulas, which follows common practice but needs care when editing a profile.
- No lap lengths, couplers, bar type or grade checks, and no revision comparison.
- Validated on self-generated synthetic data only.

## Future improvements

- Column mapping file for schedules exported from detailing software
- More shape codes and a second profile for another standard
- Comparison of two revisions of the same schedule
- Checks across schedules, for example the same drawing number issued twice
