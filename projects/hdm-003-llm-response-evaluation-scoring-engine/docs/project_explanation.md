# Project explanation

## What it is

A small program that marks LLM answers the way an exam board marks papers: with a written marking scheme (the rubric), more than one marker (the evaluators), automatic checks for the things a computer can verify, and a clear rule for pass or fail.

## Why it matters

Human evaluation of LLMs produces thousands of ratings. The ratings are only useful if they are turned into decisions the same way every time. Three problems appear in practice:

1. **Averages hide serious faults.** An answer that is clear, complete and polite but contains one invented fact can still average 4 out of 5.
2. **Human ratings can be wrong.** Evaluators get tired, rush, or read the guidelines differently. Without a cross-check nobody notices.
3. **Small differences get over-read.** A gap between two models may be noise from the particular test cases chosen.

The engine deals with each one: critical rules for the first, review flags for the second, and a bootstrap interval for the third.

## How it works, with an example

Test case C01 asks: "How long do I have to request a refund?" The case says a good answer must mention `30 days` and `order number`, must not contain `guaranteed instantly`, and should be at most 60 words.

A response says: *"You can request a refund within 30 days of purchase. Please include your order number in the request. Refunds are guaranteed instantly with no questions asked."*

1. **Automated checks.** Both required facts are found, so fact coverage is 100%. The forbidden phrase is found, so the check `forbidden_content` fails. This is a critical failure.
2. **Human ratings.** Two evaluators rate five criteria from 1 to 5. Say the means are accuracy 2, completeness 4, instruction following 3, clarity 4, safety 3.
3. **Weighted score.** Each mean is rescaled to 0-1 and multiplied by its weight:
   0.35 x 0.25 + 0.25 x 0.75 + 0.15 x 0.50 + 0.10 x 0.75 + 0.15 x 0.50 = 0.50, so the score is 50 out of 100.
4. **Verdict.** FAIL, with three reasons: `forbidden_content`, `low_critical:accuracy` (2 is below the minimum of 3) and `below_pass_score` (50 is below 70).

If the evaluators had rated accuracy 5 for this same answer, the response would still fail on the automated check, and it would also get the flag `human_auto_mismatch:accuracy`, because the people and the check disagree.

## Terms

- **Rubric**: the list of criteria used to rate a response, with a scale and weights.
- **Weight**: how much one criterion counts towards the total.
- **Critical criterion**: a criterion where a low rating fails the response regardless of the total.
- **Hallucination**: a statement in a model answer that is invented or not supported by the source. Here it is approximated by a list of forbidden phrases per test case.
- **Paired comparison**: comparing two models on the same test cases, case by case.
- **Bootstrap interval**: a way to estimate uncertainty. The test cases are re-drawn at random with replacement 2,000 times, the mean difference is recalculated each time, and the range holding the middle 95% of those values is reported. If that range includes 0, the data does not clearly favour either model.
- **Ground truth**: the known correct answer. In the sample data it is the quality profile each response was built from.

## What the sample results mean

The sample shows the engine working on data designed to exercise every rule. It does not measure any real model or any real evaluator, and the numbers must not be quoted as findings.
