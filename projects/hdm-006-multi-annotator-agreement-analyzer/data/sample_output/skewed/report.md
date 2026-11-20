# Agreement report: skewed_two_raters.csv

100 items, 2 annotators, 200 ratings. Labels treated as **nominal**: safe, unsafe.

## Headline

| Measure | Value |
|---|---|
| Raw agreement (pairs that match) | 96.0% |
| Krippendorff's alpha (nominal) | 0.694 |
| 95% bootstrap interval for alpha | 0.316 to 0.936 |
| Reading of alpha | tentative |
| Reading at the low end of the interval | unreliable |
| Fleiss' kappa | 0.693 (on 100 items with 2 ratings each) |

Reading: 0.80 and above is usually treated as reliable, 0.667 to 0.80 as usable with caution, below 0.667 as not reliable. These are conventions, not rules.

## Annotator pairs (Cohen's kappa)

| Pair | Items in common | Raw agreement | Kappa | Enough overlap |
|---|---|---|---|---|
| rater_x / rater_y | 100 | 96.0% | 0.693 | yes |

## Annotators

| Annotator | Items | Mean kappa with others | Alpha without them | Change if removed |
|---|---|---|---|---|
| rater_x | 100 | 0.693 | n/a | n/a |
| rater_y | 100 | 0.693 | n/a | n/a |

A large positive change means the team agrees better without that person's ratings. It is a reason to look at their work, not proof that they are wrong.

## Labels

| Label | Times used | Share | Alpha (this label vs the rest) |
|---|---|---|---|
| safe | 186 | 93.0% | 0.694 |
| unsafe | 14 | 7.0% | 0.694 |

## Most confused label pairs

| Label 1 | Label 2 | Share of all disagreement |
|---|---|---|
| safe | unsafe | 100.0% |

## Items to adjudicate (4 with any disagreement; most split first)

| Item | Ratings | Distinct labels | Majority | Item agreement | Labels given |
|---|---|---|---|---|---|
| msg_007 | 2 | 2 | tie | 0.0% | rater_x=unsafe; rater_y=safe |
| msg_023 | 2 | 2 | tie | 0.0% | rater_x=unsafe; rater_y=safe |
| msg_035 | 2 | 2 | tie | 0.0% | rater_x=unsafe; rater_y=safe |
| msg_064 | 2 | 2 | tie | 0.0% | rater_x=safe; rater_y=unsafe |

## Input problems (0)

None.
