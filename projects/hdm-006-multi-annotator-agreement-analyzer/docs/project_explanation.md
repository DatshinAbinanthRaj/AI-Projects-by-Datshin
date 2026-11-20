# Project explanation

## What it is

A tool that measures how consistently a group of people label the same items. It gives one headline number (Krippendorff's alpha), says how certain that number is, and then shows where the disagreement comes from.

## Why it matters

Labels made by people are the raw material for training and testing AI models. If two trained people look at the same item and give different labels, either the guideline is unclear, the task is too hard, or someone needs more training. A model trained on such labels learns the confusion.

The simple measure, "percentage of items where people agreed", looks better than it should. Imagine a spam filter project where 95 of every 100 messages are not spam. Two annotators who both press "not spam" on everything agree 100% of the time and have checked nothing. A **chance-corrected** measure asks a fairer question: how much better than luck is this agreement?

## The three statistics in plain words

- **Cohen's kappa:** two annotators. Take the agreement you saw, subtract the agreement you would expect if each person labelled at random using their own label habits, and scale the result so that 1 means perfect and 0 means "no better than luck".
- **Fleiss' kappa:** the same idea for three or more annotators, when every item has the same number of ratings.
- **Krippendorff's alpha:** the most flexible of the three. It works when some ratings are missing, with any number of annotators, and it can take the *size* of a disagreement into account. It compares the disagreement that was observed with the disagreement expected by chance: alpha = 1 - observed / expected.

## Levels of measurement

- **Nominal:** labels are names with no order (`spam`, `safe`). Any mismatch counts the same.
- **Ordinal:** labels have an order (a 1 to 5 rating). A 4 against a 5 counts as a small disagreement, a 1 against a 5 as a large one.
- **Interval:** labels are numbers and the gaps between them are equal.

Choosing the wrong level changes the answer a great deal. In the quality sample, the same ratings give alpha 0.265 when treated as names and 0.704 when treated as an ordered scale.

## How it works, step by step

1. **Read the file.** Each row becomes part of a table: for every item, who rated it and what they said. Problem rows are dropped and listed.
2. **Build the coincidence matrix.** For every item, every pair of ratings from two different people is counted: how often did `spam` meet `spam`, how often did `spam` meet `misinformation`, and so on.
3. **Calculate alpha** from that matrix, plus the two kappas.
4. **Bootstrap.** Draw a new set of items at random from the original set, with repeats allowed, and recalculate alpha. Do this 1,000 times. The middle 95% of the results is the interval. A wide interval means there is too little data to trust the number.
5. **Break it down.**
   - Remove one annotator at a time and recalculate. If alpha jumps, that annotator differs from the rest.
   - Collapse the task to "label X or not" for each label. A low value shows a label whose definition is unclear.
   - List which two labels most often land on the same item.
   - Rank items from most split to least split, ready for adjudication.
6. **Write the report** and return an exit code so a pipeline can stop when agreement is too low.

## A small example

Two annotators label 50 items as yes or no. They agree on 35, which is 70%. Annotator A says yes 25 times, annotator B says yes 30 times. By luck alone they would agree on about 50% of items (0.5 x 0.6 for yes, plus 0.5 x 0.4 for no). Kappa = (0.70 - 0.50) / (1 - 0.50) = 0.40. The 70% looked acceptable; 0.40 says the labels are only moderately better than chance. This exact case is one of the tests.

## How to read the sample results

In the moderation sample, alpha is 0.508. Two things are planted: one careless annotator and one unclear pair of labels. The tool finds both, and shows that removing the careless annotator raises alpha only to 0.635. So the bigger fix is the guideline that separates `spam` from `misinformation`, not the person.

## What it does not do

It does not say who is right. Agreement is about consistency. A team can agree perfectly and all be wrong, which is why agreement is normally used together with a gold set (items with a known correct answer).
