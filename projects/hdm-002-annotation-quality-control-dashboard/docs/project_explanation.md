# Project explanation

## What it is

A quality-control tool for data labelling work. You give it a spreadsheet where each row says "this person gave this label to this item". It tells you how reliable the labels are and where the problems sit.

## Why it matters

A machine-learning model learns from labelled examples. If the labels are wrong, the model learns the wrong thing, and nobody notices until much later. Checking labels by reading them one by one does not scale, so teams use numbers that summarise quality. The numbers are simple, but they are easy to misuse, especially when the sample is small.

## The four measurements

**Gold accuracy.** Some items are "gold": an expert already knows the right label. These are mixed into normal work. An annotator's gold accuracy is the share of gold items they got right. Example: 20 right out of 26 is 76.9%.

**The interval around accuracy.** 20 out of 26 is a small sample. If the same person labelled another 26 gold items they might get 23 right. The Wilson interval gives the plausible range for their true accuracy: here 57.9% to 89.0%. If the threshold is 80% and the range goes above it, the evidence is `weak`. Only when the whole range is below the threshold is it `strong`.

**Agreement with peers.** Most items have no gold label. But if three people label the same item, we can count how often pairs of them match. Three people give three pairs. A person whose pairs rarely match is either wrong more often or reading the guidelines differently.

**Speed and label bias.** Someone whose median time is less than 40% of the team's is probably not reading the item. Someone who uses one label much more than everyone else may be using it as a default.

## How it works, step by step

1. Read the CSV and check the six columns exist.
2. Remove rows that cannot be used (blank fields, unknown labels, duplicates) and write down each one.
3. Build every pair of annotators who labelled the same item and mark whether they agree.
4. For each annotator, calculate the four measurements and compare them with the thresholds.
5. Do the same accuracy and agreement calculation for each batch.
6. On gold items, count which correct label was given which label (the confusion matrix).
7. List the items where annotators disagree, so they can be sent for adjudication.
8. Show everything in the dashboard, or write it to files from the command line.

## A worked example

Item `i1` has gold label `x`. Annotator a says `x`, b says `x`, c says `y`.

- Gold: a and b are correct, c is wrong.
- Pairs: a-b agree, a-c disagree, b-c disagree. Agreement for this item is 1 of 3.
- The item is disputed, with majority label `x`.

This exact case is in the tests.

## What the synthetic sample teaches

The generator plants a confused annotator, a rushing annotator and a weak batch. The tool finds all three. It also flags one annotator who was generated as good, because 26 gold items were not enough to tell 91% from below 80%, and the evidence rating says so. A real quality lead would respond by adding gold items before taking any action.

## What to be careful about

- A flag starts a conversation. It does not prove poor work.
- Agreement is not accuracy. Two people can agree and both be wrong.
- A good annotator paired with poor ones gets a lower agreement rate through no fault of their own.
- Thresholds depend on the task. An 80% limit may be strict for a hard task and loose for an easy one.
