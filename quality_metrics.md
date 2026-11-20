# Quality metrics

Gate: 85/100 to publish.

| # | Relevance /15 | Technical /20 | Functionality /20 | Career relevance /15 | Docs /10 | Testing /10 | Uniqueness /10 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 001 | 13 | 16 | 18 | 14 | 9 | 9 | 8 | 87 |
| 002 | 14 | 16 | 18 | 15 | 9 | 9 | 7 | 88 |
| 003 | 13 | 17 | 18 | 14 | 9 | 9 | 8 | 88 |
| 004 | 14 | 17 | 18 | 13 | 9 | 9 | 8 | 88 |
| 005 | 14 | 16 | 18 | 15 | 9 | 9 | 7 | 88 |
| 006 | 14 | 17 | 18 | 15 | 9 | 9 | 8 | 90 |

Notes on 001: points held back for simplified bending formulas, CSV-only input, single-reviewer workflow, and validation on self-generated synthetic data only.

Notes on 002: points held back for raw (not chance-corrected) agreement, single-label tasks only, no history between uploads, dashboard checked by one headless browser run and not by automated UI tests, and validation on self-generated synthetic data only.

Notes on 003: points held back for keyword-based (not semantic) fact and hallucination checks, fixed-phrase refusal detection, plain averaging of evaluators with no chance-corrected agreement, comparison limited to two models, and validation on self-generated synthetic data only.

Notes on 004: points held back for an illustrative rule profile not verified against a purchased standard, ten shape codes only, a single input layout with no column mapping, no check against drawings, the HTML report checked by one headless browser run and not by automated UI tests, and validation on self-generated synthetic data only.

Notes on 005: points held back for an outlook based on plain averages with no range, the latest week assumed complete, calendar-hour deadlines with no working calendar, labour cost only, no interval on the weekly QA pass rate, the dashboard checked by one headless browser run and not by automated UI tests, and validation on self-generated synthetic data only.

Notes on 006: points held back for no weighted kappa, single-label ratings only, a bootstrap that treats annotators as fixed and is rough for rare labels, conventional cut-offs that do not fit every task, no gold-set comparison, and validation on self-generated synthetic data only (the formulas themselves are checked against published examples).
