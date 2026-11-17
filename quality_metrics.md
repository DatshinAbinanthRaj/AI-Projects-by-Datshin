# Quality metrics

Gate: 85/100 to publish.

| # | Relevance /15 | Technical /20 | Functionality /20 | Career relevance /15 | Docs /10 | Testing /10 | Uniqueness /10 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 001 | 13 | 16 | 18 | 14 | 9 | 9 | 8 | 87 |
| 002 | 14 | 16 | 18 | 15 | 9 | 9 | 7 | 88 |
| 003 | 13 | 17 | 18 | 14 | 9 | 9 | 8 | 88 |

Notes on 001: points held back for simplified bending formulas, CSV-only input, single-reviewer workflow, and validation on self-generated synthetic data only.

Notes on 002: points held back for raw (not chance-corrected) agreement, single-label tasks only, no history between uploads, dashboard checked by one headless browser run and not by automated UI tests, and validation on self-generated synthetic data only.

Notes on 003: points held back for keyword-based (not semantic) fact and hallucination checks, fixed-phrase refusal detection, plain averaging of evaluators with no chance-corrected agreement, comparison limited to two models, and validation on self-generated synthetic data only.
