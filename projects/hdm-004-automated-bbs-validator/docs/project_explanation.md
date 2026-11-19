# Project explanation: HDM-004

## What is it?

A program that checks bar bending schedules automatically. You point it at a folder of schedules. It tells you which ones are fine (PASS), which need a person to look at something (REVIEW) and which have definite mistakes (FAIL). For every problem it says which file, which line, which bar mark, what is wrong and, when it can, what the value should be.

## Why does it matter?

A bar bending schedule is a table that the steel fabricator works from. If a cut length or a quantity is wrong, the wrong steel is delivered. Checking by hand takes time, and people check some rows more carefully than others.

Many of the mistakes are plain arithmetic or bookkeeping:

- total bars does not equal members times bars per member
- the cut length does not match the shape and its dimensions
- the same bar mark appears twice
- the weight summary was not updated after the rows changed
- the revision or "checked by" box is empty

A program can find all of these every time. That leaves the human checker free for the questions that need engineering judgement, which a program cannot answer.

The idea is not limited to rebar. Any team that receives records made by people, such as labelled data or evaluation results, needs the same thing: clear rules, a clear verdict for each batch, and a reason for each rejection.

## How does it work?

1. **Read the rule profile.** A JSON file holds the allowed bar sizes, the bend radius and minimum leg length for each size, the rounding step, the tolerances and the formula for each shape code. The program checks this file first and refuses to continue if it is faulty.
2. **Read the schedules.** CSV files and Excel files are both turned into the same simple list of rows. The title block and the weight summary are read if they are supplied.
3. **Check each row.** Are the required cells filled? Are the numbers real numbers? Is the bar size allowed? Does total bars equal members times bars per member? Does the shape have all its dimensions? Are the end legs long enough to bend? Does the cut length match the formula?
4. **Check the whole schedule.** Is any bar mark repeated? Are the title-block fields filled in? Does the declared weight for each bar size match the weight of the rows?
5. **Give a verdict.** Any error means FAIL. Only warnings means REVIEW. Nothing found means PASS.
6. **Write the reports.** A CSV list of findings, a JSON summary for other programs and an HTML page for people.

### A simple example

Row: bar mark 02, shape code 21 (a U bar), 20 mm bar, A = 400, B = 2400, C = 400, scheduled cut length 3400 mm.

- The profile says the formula for shape 21 is `A + B + C - r - 2*d`.
- For a 20 mm bar the profile gives r = 70.
- 400 + 2400 + 400 - 70 - 40 = 3090 mm.
- Rounded up to the next 25 mm: 3100 mm.
- The schedule says 3400 mm. That is 300 mm more than expected and the tolerance is 25 mm.
- Finding: `cut_length_mismatch`, error, suggested value 3100.

## Key ideas

**Rules as data.** The formulas are in a file, not buried in the program. A different office or standard can use a different profile without touching the code.

**Safe formula evaluation.** Text from a file must not be allowed to run as a program. The tool reads each formula into a structure, checks that it contains only numbers, the letters A to E, d, r and arithmetic signs, and only then calculates it.

**Severity.** An error is wrong whatever the reason. A warning might be intentional, so a person decides.

**Reconciliation.** Comparing a declared total with the sum of the detail rows. It catches edits made in one place and forgotten in another.

**Ground truth testing.** The sample data has 29 defects planted on purpose and written down in a list. The test demands that the tool finds exactly those 29: none missed and none extra.

## What it does not do

It does not check the schedule against the drawings or the structural design. It cannot tell whether the right bars were specified, only whether the schedule agrees with itself and with the profile. The profile values are illustrative and must be verified before real use. A PASS is not an engineering approval.
