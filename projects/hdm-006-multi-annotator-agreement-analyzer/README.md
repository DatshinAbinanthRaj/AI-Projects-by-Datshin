# HDM-006: Multi-Annotator Agreement Analyzer

A command-line tool that reads a file of human ratings and answers one question properly: **do the annotators agree more than they would by luck?** It reports chance-corrected agreement (Cohen's kappa, Fleiss' kappa, Krippendorff's alpha), shows how sure the number is, and points to the annotators, labels and items that cause the disagreement.

> Prototype on **synthetic data**. The numbers are prompts for a closer look at guidelines and training, not judgements about people.

## Business problem

Before a labelled dataset is used to train or evaluate a model, someone has to decide whether the labels can be trusted. The usual first number is "the annotators agreed on 90% of items". That number misleads in two common situations:

- **One label dominates.** If 95% of items are `safe`, two people who both answer `safe` almost every time agree about 90% of the time even when neither of them recognises an unsafe item.
- **Near misses are counted as full misses.** On a 1 to 5 scale, a 4 against a 5 is a small difference, a 1 against a 5 is a large one. Plain agreement treats them the same.

Real projects add two more complications: not every annotator sees every item, and one number for the whole team does not say what to fix.

## Solution

1. Load ratings in **long** layout (one row per rating) or **wide** layout (one column per annotator, empty cells allowed), listing every row that was dropped and why.
2. Calculate raw agreement, **Krippendorff's alpha** (any number of annotators, missing ratings allowed; nominal, ordinal or interval labels), **Fleiss' kappa** and **Cohen's kappa** for every pair.
3. Put a **95% bootstrap interval** around alpha, and read the result at the low end of that interval as well as at the point value.
4. Break the result down: per annotator (average kappa with the others, and what alpha becomes if that person's ratings are removed), per label (alpha for "this label against everything else"), the most confused label pairs, and a ranked list of items to send to adjudication.

## Features

- Three agreement statistics, each checked against published worked examples
- Nominal, ordinal and interval treatment of labels (`--level`)
- Works with missing ratings and unequal numbers of ratings per item
- Bootstrap confidence interval with a fixed seed, so results repeat
- "Alpha without this annotator" diagnostic
- Per-label agreement and confused label pairs
- Adjudication list, most split items first
- Input validation with a full list of problems (blank fields, duplicates, unknown labels, single-rating items)
- Markdown, JSON and CSV outputs; exit code usable as a quality gate in a pipeline
- No third-party packages needed to run it

## Architecture

```
ratings CSV (long or wide)
      |
loaders.load_ratings  ->  units {item: {annotator: label}}  +  list of input problems
      |
metrics.py   percent agreement, Cohen, Fleiss, Krippendorff (coincidence matrix)
      |
analysis.py  bootstrap interval, pair table, annotator table, label table,
             confused pairs, items to adjudicate
      |
report.py    report.md, summary.json, CSV tables     run.py  exit code 0 / 1 / 2
```

See [docs/architecture.md](docs/architecture.md) and [docs/project_explanation.md](docs/project_explanation.md).

## Technology

Python 3.10+ standard library only (`csv`, `collections`, `itertools`, `random`, `argparse`, `json`). pytest for the tests.

## Install and run

```bash
pip install -r requirements.txt        # only pytest

python run.py analyse data/moderation_long.csv --out-dir out
python run.py analyse data/quality_wide.csv --level ordinal --order 1,2,3,4,5 --out-dir out
python run.py analyse data/skewed_two_raters.csv --out-dir out
python run.py analyse data/invalid/problems_long.csv --labels cat,dog --out-dir out
python run.py generate                 # rebuild the sample data
python -m pytest
```

Options: `--layout auto|long|wide`, `--level nominal|ordinal|interval`, `--order` (ordinal: labels from lowest to highest), `--labels` (allowed labels), `--min-alpha` (default 0.667), `--min-overlap` (default 10), `--bootstrap` (default 1000, 0 to skip), `--seed`.

Exit code: `0` alpha meets `--min-alpha`, `1` alpha is below it or cannot be calculated, `2` the input could not be used.

## Input

Long layout:

| item_id | annotator_id | label |
|---|---|---|
| post_001 | ann_2 | safe |
| post_001 | ann_3 | harassment |

Wide layout (first column `item_id`, then one column per annotator; empty means "did not rate"):

| item_id | rater_a | rater_b | rater_c | rater_d |
|---|---|---|---|---|
| resp_001 | 3 | 3 |  | 4 |

## Sample data

All files in `data/` are synthetic, produced by `src/agreement/generate.py` with fixed seeds.

| File | What it is | Planted on purpose |
|---|---|---|
| `moderation_long.csv` | 150 invented posts, 4 moderation labels, 5 annotators, 3 per item | `spam` and `misinformation` swapped 30% of the time by everyone; `ann_5` is 70% accurate |
| `moderation_truth.csv` | the generated "true" label per post | not used by the tool; kept for reference |
| `quality_wide.csv` | 80 invented model responses rated 1 to 5 by 4 raters, about 10% empty cells | `rater_d` scores one point higher |
| `skewed_two_raters.csv` | 100 messages, 2 raters, 5% `unsafe` | high raw agreement, lower kappa |
| `invalid/problems_long.csv` | 9 hand-written rows with input problems | duplicate rating, unknown label, blank annotator |
| `invalid/missing_columns.csv` | wrong column names | must be rejected |

## Example output

From `data/sample_output/` (full reports are in that folder):

| Sample | Raw agreement | Alpha | 95% interval | Reading | Exit code |
|---|---|---|---|---|---|
| moderation (nominal) | 66.0% | 0.508 | 0.434 to 0.583 | unreliable | 1 |
| quality (ordinal) | 43.9% | 0.704 | 0.602 to 0.770 | tentative; unreliable at the low end | 0 |
| quality, order ignored | 43.9% | 0.265 | - | - | - |
| skewed (nominal) | 96.0% | 0.694 | 0.316 to 0.936 | tentative; unreliable at the low end | 0 |

Moderation sample, annotator table:

| Annotator | Items | Mean kappa with others | Alpha without them | Change if removed |
|---|---|---|---|---|
| ann_1 | 90 | 0.564 | 0.475 | -0.033 |
| ann_2 | 96 | 0.568 | 0.459 | -0.049 |
| ann_3 | 98 | 0.502 | 0.475 | -0.033 |
| ann_4 | 92 | 0.538 | 0.492 | -0.016 |
| ann_5 | 74 | 0.287 | 0.635 | +0.127 |

The most confused pair is `misinformation` / `spam`, with 34.6% of all disagreement.

## Validation

- **30 automated tests**, all passing.
- **Published examples:** Krippendorff's 4-observer, 12-unit example with missing ratings gives 0.743 (nominal), 0.815 (ordinal) and 0.849 (interval); Fleiss' 1971 example gives 0.210. The tests check all four values.
- **Hand-calculated cases:** a 2x2 Cohen's kappa of 0.40, pair counting for raw agreement, perfect agreement (1), systematic disagreement (below 0), and single-label data (reported as undefined instead of crashing).
- **Independent libraries (one-off check, not part of the tests):** on the sample files, Cohen's kappa matched scikit-learn's `cohen_kappa_score`, and alpha at all three levels matched the `krippendorff` package, to six decimal places.
- The committed sample files are checked against the generator output, so they cannot drift.

What the sample runs show, and what they do not:

- The tool found all three planted problems: the `spam` / `misinformation` confusion, `ann_5`, and `rater_d`.
- Removing `ann_5` lifts alpha only to 0.635, still under 0.667. The guideline problem is larger than the annotator problem. This is the kind of result that changes what a manager does next.
- On the quality sample the point value passes the 0.667 bar but the low end of the interval (0.602) does not. With 80 items, the sample is too small to be sure.
- On the skewed sample the interval runs from 0.316 to 0.936. With only about five `unsafe` items, the data cannot say whether the raters are reliable on the rare class, whatever the 96% suggests.
- These results come from data built to contain these problems. They show that the calculations work. They say nothing about how often such problems occur in real projects.

## Business applications

Acceptance check before a labelled batch goes to model training; pilot rounds for new annotation guidelines; choosing which label definitions to rewrite; evaluator calibration for LLM rating tasks; choosing items for adjudication; evidence in vendor quality reviews; an automatic gate in a data pipeline.

## Skills demonstrated

Inter-annotator agreement (Cohen, Fleiss, Krippendorff), chance correction, levels of measurement, handling of missing ratings, bootstrap confidence intervals, diagnostic breakdown by annotator, label and item, input validation, verification against published reference values, command-line tool design.

## Limitations

- The 0.80 and 0.667 cut-offs are conventions. The right bar depends on what the labels are for.
- "Alpha without this annotator" shows who differs from the group. The group can be the one that is wrong.
- Fleiss' kappa uses only the items that have the most common number of ratings; the report states how many.
- The bootstrap resamples items and treats the annotators as fixed. Intervals are wide and rough when there are few items or a rare label.
- One label per rating. No multi-label tasks, text spans, bounding boxes or rankings.
- No weighted Cohen's kappa; use ordinal alpha for ordered labels.
- Everything is held in memory; not designed for millions of ratings.

## Future improvements

Weighted kappa; agreement against a gold set alongside agreement between annotators; trend across batches; suggested number of items for a target interval width; an HTML report.
