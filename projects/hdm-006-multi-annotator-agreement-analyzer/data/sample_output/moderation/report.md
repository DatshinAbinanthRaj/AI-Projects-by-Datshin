# Agreement report: moderation_long.csv

150 items, 5 annotators, 450 ratings. Labels treated as **nominal**: harassment, misinformation, safe, spam.

## Headline

| Measure | Value |
|---|---|
| Raw agreement (pairs that match) | 66.0% |
| Krippendorff's alpha (nominal) | 0.508 |
| 95% bootstrap interval for alpha | 0.434 to 0.583 |
| Reading of alpha | unreliable |
| Reading at the low end of the interval | unreliable |
| Fleiss' kappa | 0.507 (on 150 items with 3 ratings each) |

Reading: 0.80 and above is usually treated as reliable, 0.667 to 0.80 as usable with caution, below 0.667 as not reliable. These are conventions, not rules.

## Annotator pairs (Cohen's kappa)

| Pair | Items in common | Raw agreement | Kappa | Enough overlap |
|---|---|---|---|---|
| ann_1 / ann_2 | 46 | 80.4% | 0.666 | yes |
| ann_1 / ann_3 | 48 | 79.2% | 0.703 | yes |
| ann_1 / ann_4 | 52 | 71.2% | 0.601 | yes |
| ann_1 / ann_5 | 34 | 50.0% | 0.286 | yes |
| ann_2 / ann_3 | 53 | 73.6% | 0.595 | yes |
| ann_2 / ann_4 | 46 | 80.4% | 0.694 | yes |
| ann_2 / ann_5 | 47 | 51.1% | 0.315 | yes |
| ann_3 / ann_4 | 57 | 64.9% | 0.509 | yes |
| ann_3 / ann_5 | 38 | 42.1% | 0.200 | yes |
| ann_4 / ann_5 | 29 | 51.7% | 0.347 | yes |

## Annotators

| Annotator | Items | Mean kappa with others | Alpha without them | Change if removed |
|---|---|---|---|---|
| ann_1 | 90 | 0.564 | 0.475 | -0.033 |
| ann_2 | 96 | 0.568 | 0.459 | -0.049 |
| ann_3 | 98 | 0.502 | 0.475 | -0.033 |
| ann_4 | 92 | 0.538 | 0.492 | -0.016 |
| ann_5 | 74 | 0.287 | 0.635 | +0.127 |

A large positive change means the team agrees better without that person's ratings. It is a reason to look at their work, not proof that they are wrong.

## Labels

| Label | Times used | Share | Alpha (this label vs the rest) |
|---|---|---|---|
| harassment | 68 | 15.1% | 0.551 |
| misinformation | 65 | 14.4% | 0.318 |
| safe | 202 | 44.9% | 0.650 |
| spam | 115 | 25.6% | 0.417 |

## Most confused label pairs

| Label 1 | Label 2 | Share of all disagreement |
|---|---|---|
| misinformation | spam | 34.6% |
| safe | spam | 21.6% |
| harassment | safe | 19.6% |
| misinformation | safe | 9.8% |
| harassment | spam | 9.2% |
| harassment | misinformation | 5.2% |

## Items to adjudicate (74 with any disagreement; most split first)

| Item | Ratings | Distinct labels | Majority | Item agreement | Labels given |
|---|---|---|---|---|---|
| post_015 | 3 | 3 | tie | 0.0% | ann_2=spam; ann_3=misinformation; ann_5=harassment |
| post_037 | 3 | 3 | tie | 0.0% | ann_1=spam; ann_2=safe; ann_5=harassment |
| post_051 | 3 | 3 | tie | 0.0% | ann_1=harassment; ann_2=safe; ann_3=misinformation |
| post_096 | 3 | 3 | tie | 0.0% | ann_2=safe; ann_3=harassment; ann_5=spam |
| post_123 | 3 | 3 | tie | 0.0% | ann_3=harassment; ann_4=safe; ann_5=spam |
| post_001 | 3 | 2 | safe | 33.3% | ann_2=safe; ann_3=harassment; ann_4=safe |
| post_002 | 3 | 2 | misinformation | 33.3% | ann_1=misinformation; ann_2=spam; ann_5=misinformation |
| post_003 | 3 | 2 | harassment | 33.3% | ann_1=misinformation; ann_2=harassment; ann_5=harassment |
| post_004 | 3 | 2 | safe | 33.3% | ann_3=safe; ann_4=harassment; ann_5=safe |
| post_006 | 3 | 2 | safe | 33.3% | ann_1=safe; ann_2=safe; ann_5=spam |
| post_007 | 3 | 2 | spam | 33.3% | ann_1=spam; ann_4=spam; ann_5=misinformation |
| post_010 | 3 | 2 | spam | 33.3% | ann_1=spam; ann_3=spam; ann_4=safe |
| post_013 | 3 | 2 | misinformation | 33.3% | ann_1=misinformation; ann_2=misinformation; ann_5=spam |
| post_017 | 3 | 2 | spam | 33.3% | ann_1=spam; ann_3=spam; ann_4=safe |
| post_018 | 3 | 2 | safe | 33.3% | ann_2=safe; ann_3=safe; ann_5=spam |

## Input problems (0)

None.
