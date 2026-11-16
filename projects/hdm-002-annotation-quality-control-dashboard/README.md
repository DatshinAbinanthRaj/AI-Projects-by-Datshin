# HDM-002: AI Annotation Quality Control Dashboard

A dashboard and command-line tool that reads an annotation export and answers the questions a data operations lead asks every week: how good are the labels, which annotators need attention, which batch went wrong, and which items need a second opinion.

> Prototype on **synthetic data**. Flags are prompts for a closer look, not judgements about people.

## Business problem

AI teams pay people to label data, and model quality depends on those labels. Quality problems are usually hidden inside a large spreadsheet: one annotator who mixes up two classes, another who rushes, a batch where the guidelines were misread. Finding these by hand is slow, and small samples make it easy to blame the wrong person.

## Solution

Take one CSV (one row per label given), clean it, and measure quality four ways:

1. **Gold accuracy**: on items where the correct answer is known, how often is each annotator right? Shown with a 95% Wilson interval so small samples are not over-read.
2. **Agreement with peers**: when two annotators label the same item, how often do they match?
3. **Speed**: median time per item compared with the team median.
4. **Label bias**: does one annotator use a label far more or less than everyone else?

Results are shown per annotator and per batch, with a confusion matrix and a list of disputed items.

## Features

- Streamlit dashboard: file upload, adjustable thresholds, overview tiles, charts, tables, report download
- Command-line check that writes a Markdown report, JSON summary and CSV tables
- Input validation that lists every dropped or repaired row (blank fields, unknown labels, duplicates, bad times, conflicting gold labels)
- Four flags: `LOW_GOLD_ACCURACY`, `LOW_AGREEMENT`, `TOO_FAST`, `LABEL_BIAS`
- Minimum sample sizes before a flag can fire, and an evidence rating (`strong` / `weak`) for accuracy flags
- Synthetic data generator with three planted problems

## Architecture

```
annotation CSV -> qc.validate -> clean rows + issue list
                      |
        annotator / batch / item / confusion metrics (qc.py)
                      |
      +---------------+----------------+
   app.py (Streamlit dashboard)   run.py check (report.md, summary.json, CSVs)
```

See [docs/architecture.md](docs/architecture.md) and [docs/project_explanation.md](docs/project_explanation.md).

## Technology

Python 3.10+, pandas (metrics), Streamlit (dashboard), Plotly (charts), pytest (tests).

## Install and run

```bash
pip install -r requirements.txt

streamlit run app.py                                         # dashboard, opens with the sample data
python run.py check data/sample_annotations.csv --out-dir out   # same analysis on the command line
python run.py check data/sample_invalid.csv --out-dir out --labels billing,technical,account,other
python run.py generate                                       # rebuild the sample data (seed 11)
python -m pytest
```

`run.py check` exits with 0 when nobody is flagged, 1 when someone is, and 2 when the file cannot be read.

## Input

| Column | Meaning |
|---|---|
| `item_id` | the thing being labelled |
| `annotator_id` | who labelled it |
| `label` | the label given |
| `gold_label` | the known correct label; blank for normal items |
| `batch` | work batch or date |
| `seconds_spent` | time taken for this label |

## Sample data

`data/sample_annotations.csv` is synthetic: 120 invented support tickets, four intent labels, five annotators, three labels per item, 36 gold items. It is produced by `src/annotation_qc/generate.py` with seed 11. Three problems are planted on purpose:

| Planted problem | Where |
|---|---|
| Confuses `technical` and `account` (70% accurate) | `ann_d` |
| Rushes (about 9 s per item) and falls back on `other` (68% accurate) | `ann_e` |
| Everyone 12 points less accurate | batch `B4` |

`ann_a`, `ann_b` and `ann_c` are generated as good annotators (96%, 93%, 91%).

`data/sample_invalid.csv` is a small hand-written file with seven validation problems.

## Example output

From `data/sample_output/report.md`:

| Annotator | Gold correct | Gold accuracy | 95% interval | Agreement | Speed ratio | Flags | Evidence |
|---|---|---|---|---|---|---|---|
| ann_a | 18/19 | 94.7% | 75.4% to 99.1% | 74.3% | 1.13 | - | - |
| ann_b | 17/18 | 94.4% | 74.2% to 99.0% | 73.3% | 1.16 | - | - |
| ann_c | 20/26 | 76.9% | 57.9% to 89.0% | 68.9% | 0.96 | LOW_GOLD_ACCURACY, LOW_AGREEMENT | weak |
| ann_d | 14/21 | 66.7% | 45.4% to 82.8% | 63.0% | 1.10 | LOW_GOLD_ACCURACY, LOW_AGREEMENT | weak |
| ann_e | 19/24 | 79.2% | 59.5% to 90.8% | 65.1% | 0.27 | LOW_GOLD_ACCURACY, LOW_AGREEMENT, TOO_FAST | weak |

Batch `B4` has the lowest agreement (51.1%, against 67.8% to 78.9% for the others).

## Validation

- 23 automated tests: hand-calculated small cases for every metric, the Wilson interval against a known value, each validation rule, each flag, the command line, and a check that the committed sample equals the generator output.
- The dashboard was started headless and loaded in a browser: all five tabs rendered with no errors, the invalid sample showed its issues, and a file with missing columns showed a clear error message.

What the sample run shows, and what it does not:

- Found: `ann_d` (low accuracy), `ann_e` (too fast, leans on `other`), and the drop in batch `B4`.
- **False alarm:** `ann_c` was generated as a 91% annotator but scored 20/26 on gold and was flagged. The evidence rating is `weak` and the interval reaches 89%, which is the tool saying "not enough gold items to be sure". This is the main lesson of the sample: about 20 gold items per person cannot separate an 80% annotator from a 90% one.
- No accuracy flag reached `strong` evidence at this sample size.
- `ann_e`'s label bias is 19.8 points, just under the 20-point limit, so `LABEL_BIAS` did not fire.
- These results come from data built to contain these problems. They show the calculations work; they say nothing about how often such problems occur in real projects.

## Business applications

Weekly quality review of a labelling vendor or in-house team; deciding who needs retraining; catching guideline drift between batches; choosing items for adjudication; evidence for quality clauses in a vendor contract.

## Skills demonstrated

Annotation quality metrics, gold-set accuracy, confidence intervals on small samples, peer agreement, annotator behaviour signals, data validation, dashboard design, test-driven metric code.

## Limitations

- Agreement is raw percent agreement, not corrected for chance, and a good annotator's rate falls when their peers are poor.
- Label bias assumes items are assigned at random; if one person gets a different mix of items, the flag misleads.
- Single-label classification only. No spans, boxes, rankings or free text.
- One time value per label; no handling of breaks or idle time.
- Thresholds are starting points and must be set for each task.
- No login, no storage, no history between uploads.

## Future improvements

Chance-corrected agreement; trends across weeks; per-class accuracy by annotator; suggested gold-set size for a target interval width; export of a retraining list.
