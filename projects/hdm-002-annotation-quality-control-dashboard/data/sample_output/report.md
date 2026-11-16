# Annotation quality report: sample_annotations.csv

- Rows received: 360, used: 360, validation issues: 0
- Items: 120 (36 gold), annotators: 5
- Gold accuracy (all annotators): 81.5%
- Pairwise agreement: 68.9%
- Disputed items: 50 (41.7% of items with 2+ labels)
- Flagged annotators: ann_c, ann_d, ann_e

## Annotators

| Annotator | Labels | Gold correct | Gold accuracy | 95% interval | Agreement | Speed ratio | Label bias | Flags | Accuracy evidence |
|---|---|---|---|---|---|---|---|---|---|
| ann_a | 72 | 18/19 | 94.7% | 75.4% to 99.1% | 74.3% | 1.13 | 6 pts (billing) | - | - |
| ann_b | 73 | 17/18 | 94.4% | 74.2% to 99.0% | 73.3% | 1.16 | 8 pts (other) | - | - |
| ann_c | 66 | 20/26 | 76.9% | 57.9% to 89.0% | 68.9% | 0.96 | 10 pts (technical) | LOW_GOLD_ACCURACY, LOW_AGREEMENT | weak |
| ann_d | 73 | 14/21 | 66.7% | 45.4% to 82.8% | 63.0% | 1.10 | 17 pts (account) | LOW_GOLD_ACCURACY, LOW_AGREEMENT | weak |
| ann_e | 76 | 19/24 | 79.2% | 59.5% to 90.8% | 65.1% | 0.27 | 20 pts (other) | LOW_GOLD_ACCURACY, LOW_AGREEMENT, TOO_FAST | weak |

Accuracy evidence is `strong` only when the whole 95% interval is below the threshold; `weak` means the gold sample is too small to be sure.

## Batches

| Batch | Labels | Gold accuracy | Agreement |
|---|---|---|---|
| B1 | 90 | 81.5% | 67.8% |
| B2 | 90 | 88.9% | 77.8% |
| B3 | 90 | 77.8% | 78.9% |
| B4 | 90 | 77.8% | 51.1% |

## Confusion on gold items (rows = correct label, columns = label given)

| gold \ given | account | billing | other | technical |
|---|---|---|---|---|
| account | 20 | 1 | 2 | 1 |
| billing | 2 | 23 | 1 | 1 |
| other | 4 | 1 | 16 | 0 |
| technical | 4 | 1 | 2 | 29 |

## Thresholds used

- min_accuracy: 0.8
- min_gold: 10
- min_agreement: 0.7
- min_pairs: 20
- min_speed_ratio: 0.4
- max_label_bias: 0.2

A flag is a reason to look closer, not a verdict about a person.
