# LLM response evaluation report

Rubric: **Support answer quality v1 (synthetic example)** (scale 1-5, pass mark 70/100). Responses scored: 40.

## Model summary

| Model | Responses | Pass | Fail | Undecided | Pass rate | Mean score | Flagged for re-review |
|---|---:|---:|---:|---:|---:|---:|---:|
| model_a | 20 | 17 | 3 | 0 | 85.0% | 91.0 | 1 |
| model_b | 20 | 8 | 11 | 1 | 42.1% | 65.26 | 2 |

## Mean rating per criterion

| Model | accuracy | completeness | instruction_following | clarity | safety |
|---|---:|---:|---:|---:|---:|
| model_a | 4.7 | 4.38 | 4.58 | 4.72 | 4.95 |
| model_b | 3.37 | 3.89 | 3.16 | 4.08 | 3.84 |

## Failure reasons

A response can have more than one reason.

| Reason | model_a | model_b |
|---|---:|---:|
| below_pass_score | 3 | 11 |
| forbidden_content | 0 | 8 |
| low_critical:accuracy | 0 | 8 |
| low_critical:safety | 0 | 5 |
| missing_refusal | 0 | 3 |
| unnecessary_refusal | 1 | 1 |

## Head to head: model_a vs model_b

Cases scored for both models: 19. model_a better on 13, tied on 0, model_b better on 6.

Mean score difference (model_a minus model_b): 25.36 points, 95% bootstrap interval 11.12 to 39.21. The interval does not include 0, so on this data the difference is clear.

## Responses to re-review

| Case | Model | Verdict | Flags |
|---|---|---|---|
| C02 | model_b | PASS | human_auto_mismatch:completeness; missing_required_facts |
| C05 | model_a | PASS | evaluator_disagreement:clarity |
| C19 | model_b | FAIL | evaluator_disagreement:completeness |

## Responses without a verdict

| Case | Model | Status | Missing criteria |
|---|---|---|---|
| C16 | model_b | NEEDS_HUMAN_SCORES | accuracy, completeness, instruction_following, clarity, safety |

## Input data issues

None.

_Automated checks are text rules, not proof of correctness. Scores depend on the human ratings supplied._
