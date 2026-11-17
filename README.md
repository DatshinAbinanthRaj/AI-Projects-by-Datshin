# HDM-003: LLM Response Evaluation and Scoring Engine

A command-line engine that scores LLM responses against a weighted rubric. It combines human ratings with automated text checks, gives every response a PASS or FAIL with the reasons, compares two models on the same test cases, and points out the responses where the human ratings look doubtful.

All data in this folder is synthetic. The "models" are scripted text templates and the "evaluators" are random numbers. See [Sample data](#sample-data).

## Business problem

Teams that evaluate LLMs usually collect human ratings on a rubric (accuracy, completeness, safety and so on). Turning those ratings into a decision is where things go wrong:

- Ratings sit in spreadsheets and each person totals them differently.
- A response with one serious problem (an invented fact, a missing refusal) can still get a good average.
- Nobody checks whether the human ratings agree with what can be verified objectively.
- "Model A scored 4 points higher" is reported without asking whether the gap is larger than the noise.

## Solution

One rubric file defines the criteria, weights, pass mark and critical criteria. The engine then applies the same rules to every response:

1. **Automated checks** read the response text: required facts present, forbidden claims absent, word limit respected, refusal given when (and only when) it is expected.
2. **Human ratings** from one or more evaluators are averaged per criterion and combined into a weighted score from 0 to 100.
3. **Verdict rules** fail a response if an automated critical check fails, if a critical criterion is rated too low, or if the score is under the pass mark. Every reason is kept.
4. **Review flags** mark responses where evaluators disagree with each other, or where humans rated a response highly although an objective check contradicts them.
5. **Model comparison** reports pass rate, mean score, failure reasons, win/tie/loss counts and a 95% bootstrap interval for the score difference.

## Features

- Rubric as a JSON file, validated before use (weights must add up to 1, ids unique, critical minimum inside the scale); all problems are listed in one error message
- Four automated checks with a clear split between critical failures and warnings
- Weighted 0-100 score from any number of evaluators
- Critical criteria: a low accuracy or safety rating fails the response whatever the total
- Statuses `NEEDS_HUMAN_SCORES` and `INCOMPLETE_SCORES` instead of guessing when ratings are missing
- Flags `evaluator_disagreement` and `human_auto_mismatch` to send responses back for a second look
- Paired model comparison with a seeded, repeatable bootstrap interval
- Input problems (score outside the scale, unknown criterion, duplicate rating) are dropped and listed, never silently ignored
- Outputs: `results.csv`, `summary.json`, `report.md`

## Architecture

```
rubric.json   test_cases.jsonl   responses.csv   human_scores.csv
     |               |                 |                |
  rubric.py      loaders.py  (validate, list every data issue)
     \_______________|_________________|________________/
                              |
                        scoring.py  <-- checks.py (automated text checks)
                              |
                        compare.py  (per-model summary, paired bootstrap)
                              |
                        report.py   -> results.csv, summary.json, report.md
```

More detail in [docs/architecture.md](docs/architecture.md).

## Technology

Python 3.10+ standard library only (`json`, `csv`, `statistics`, `random`, `argparse`, `dataclasses`). pytest for the tests. No pandas was needed: the data is small and the logic is rule-based, so fewer dependencies means easier installation and review.

## Install and run

```bash
pip install -r requirements.txt        # only installs pytest
python run.py generate                 # rewrite the synthetic sample data in data/
python run.py score --out-dir out      # score the sample data
python -m pytest -q                    # run the tests
```

With your own files:

```bash
python run.py score --rubric my_rubric.json --cases my_cases.jsonl \
    --responses my_responses.csv --scores my_scores.csv --out-dir out
python run.py score --scores "" --out-dir out     # automated checks only
```

Exit code 0 means the run finished; 2 means an input file could not be used.

## Input

| File | Format | Content |
|---|---|---|
| Rubric | JSON | `name`, `scale_min`, `scale_max`, `pass_score`, `criteria` (each with `id`, `weight`, optional `critical` and `critical_min`), optional `disagreement_gap` and `auto_links` |
| Test cases | JSON Lines | `case_id`, `prompt`, `required_facts`, `forbidden_phrases`, `max_words`, `expect_refusal` |
| Responses | CSV | `case_id`, `model`, `response` |
| Human scores | CSV | `case_id`, `model`, `evaluator`, `criterion`, `score` |

A required fact can list alternatives with `|`, for example `order number|order id`. Matching ignores upper/lower case and extra spaces.

## Sample data

Created by `src/llm_eval/generate.py` with a fixed random seed, so it can be rebuilt exactly.

- 20 test cases about a fictional company ("Northbay Cloud"): 16 questions with required facts and 4 requests that should be refused.
- 2 scripted "models", 40 responses. Each response is built from a quality profile: good, partial (a fact missing), hallucinated (an invented claim added), verbose (over the word limit), unnecessary refusal, good refusal, missing refusal. `model_b` is given more defects on purpose.
- 2 simulated evaluators, 390 ratings: the typical rating for the profile plus small random noise.
- `data/sample_truth.csv` records the profile of each response. The tests use it as ground truth.
- Three planted situations: evaluators over-rate an incomplete answer (C02 / model_b), evaluators disagree on clarity (C05 / model_a), one response has no ratings (C16 / model_b).
- `data/invalid/` holds a rubric whose weights add up to 1.15 with a critical minimum outside the scale, and a ratings file with five bad rows.

## Example output

From `data/sample_output/report.md` (synthetic data):

| Model | Responses | Pass | Fail | Undecided | Pass rate | Mean score | Flagged for re-review |
|---|---:|---:|---:|---:|---:|---:|---:|
| model_a | 20 | 17 | 3 | 0 | 85.0% | 91.0 | 1 |
| model_b | 20 | 8 | 11 | 1 | 42.1% | 65.26 | 2 |

> Mean score difference (model_a minus model_b): 25.36 points, 95% bootstrap interval 11.12 to 39.21.

| Case | Model | Verdict | Flags |
|---|---|---|---|
| C02 | model_b | PASS | human_auto_mismatch:completeness; missing_required_facts |
| C05 | model_a | PASS | evaluator_disagreement:clarity |

C02 shows why the mismatch flag exists: the answer leaves out a required fact, both evaluators still rated completeness 5, and the response passed. The flag sends it back for a second look.

The invalid rubric gives:

```
ERROR: invalid rubric: criterion 'safety' critical_min must be inside the scale; weights add up to 1.1500, they must add up to 1
```

## Validation

- 38 automated tests, all passing (`python -m pytest -q`).
- The tests cover: rubric validation (9 invalid variants), each automated check including the word-limit boundary, a hand-calculated weighted score, every verdict rule, both review flags, the comparison counts, file loading errors, and the command line.
- End-to-end test against the ground truth: every planted hallucination, missing refusal and unnecessary refusal is failed with the right reason, and no clean response gets a critical failure.

What this does and does not prove: the results show that the engine applies its rules correctly to data built for it. The model scores, pass rates and the gap between the models are properties of the generator settings and say nothing about any real model or real evaluators.

## Business applications

- Release decisions: one repeatable PASS/FAIL process for a model or prompt version
- Vendor or model selection with an honest statement of uncertainty
- Evaluator quality control: finding ratings that need a second opinion
- A shared rubric file that operations, quality and engineering can all read

## Skills demonstrated

Rubric design and validation, weighted scoring, critical-failure rules, automated response checks, combining human and automated evaluation, evaluator disagreement signals, paired model comparison with a bootstrap interval, failure categorisation, input data validation, synthetic test data with ground truth, Python CLI, pytest.

## Limitations

- Automated checks are keyword rules. A fact stated in different words is counted as missing, and a forbidden phrase is found even inside a correct sentence such as "this is not guaranteed".
- Refusal detection looks for six fixed English phrases.
- Human ratings are averaged. There is no chance-corrected agreement statistic and no weighting by evaluator reliability.
- The comparison handles exactly two models. With one model, or three or more, only the per-model summary is produced.
- The bootstrap interval treats test cases as independent and is rough on small samples.
- Validated on self-generated synthetic data only.

## Future improvements

- Chance-corrected agreement (Cohen's kappa, Krippendorff's alpha) per criterion
- Pluggable checks, for example a regular-expression check or a JSON-format check
- Comparison across more than two models and across rubric versions
- Regression mode: compare a new run against a saved baseline
