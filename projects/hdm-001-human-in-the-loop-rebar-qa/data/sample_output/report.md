# Rebar QA run report

Synthetic demonstration data. Prototype output: requires engineering review.

## Routing

| Route | Rows |
|---|---:|
| Auto-accepted | 28 |
| Auto-flagged (returned to detailer) | 18 |
| Human review | 11 |
| QA sample of clean rows | 3 |
| **Total** | **60** |

- Automation rate (rows needing no human): 76.7 %
- Reviews still pending: 0

## Human review outcomes

- Human-review rows decided: 11 (5 confirmed issues, 6 false alarms, false-alarm rate 54.5 %)
- QA-sampled clean rows decided: 3 (0 escaped defects, escape rate 0.0 %)

## Findings by rule

| Rule | Type | Findings | Confirmed by human | False alarm |
|---|---|---:|---:|---:|
| cut_length_deviation | needs judgement | 7 | 3 | 4 |
| cut_length_error | certain | 3 | - | - |
| duplicate_bar_mark | certain | 2 | - | - |
| exceeds_stock_length | needs judgement | 2 | 2 | 0 |
| missing_value | certain | 2 | - | - |
| non_standard_diameter | certain | 2 | - | - |
| total_bars_mismatch | certain | 3 | - | - |
| total_weight_mismatch | certain | 3 | - | - |
| unit_weight_mismatch | certain | 3 | - | - |
| unsupported_shape_code | needs judgement | 2 | 0 | 2 |
