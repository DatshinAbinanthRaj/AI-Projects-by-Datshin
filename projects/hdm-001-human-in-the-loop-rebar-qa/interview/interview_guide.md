# Interview guide: HDM-001

## 30-second explanation

"I built a small human-in-the-loop QA tool for rebar schedules. It runs automatic checks, but instead of trusting them blindly it separates errors a machine can be sure about from ones that need a person. Sure errors go straight back with a suggested fix, unclear ones go to a review queue, and a random sample of the accepted rows is also checked by a human. Then it reports how often the checks were right. It is the same pattern used to manage annotation and AI evaluation quality."

## 90-second explanation

**Problem.** Checking a bar bending schedule fully by hand is slow, and fully by script is risky, because some deviations are judgement calls. AI data pipelines have the same problem with labels and model outputs.

**Approach.** I split findings into certain and needs-judgement, and route each row to auto-accept, auto-flag or human review. I added a random QA sample of accepted rows, because that is the only way to see what the rules miss.

**Implementation.** Python with the standard library. The checks are pure functions. Routing and the decision log use SQLite, and decisions are append-only so there is an audit trail. Everything runs from the command line.

**Validation.** I generated a synthetic schedule with known injected defects and wrote 28 tests. On the sample file all injected defects were caught and no clean row was wrongly flagged.

**Outcome.** About three quarters of the sample rows needed no human, and the report shows the false-alarm rate per rule, which tells you which threshold to adjust. The limits are clear: the data is synthetic and the reviewer was simulated, so it proves the workflow, not real-world accuracy.

## Five likely questions

**1. How did you decide what goes to a human?**
By the type of rule, not by a score. Arithmetic checks (total bars = members x bars per member) are either right or wrong, so they are "certain". A cut length 50 mm off could be rounding, an allowance or a mistake, so that rule is "needs judgement". Any row with one judgement finding goes to a human.

**2. Why sample rows that passed every check?**
Rules only catch what they were written for. A QA sample (here 10 % of clean rows) lets a human look for anything else. The share of sampled rows with a problem is the *escape rate*: an estimate of defects getting through the automation.

**3. What is a false-alarm rate and why track it per rule?**
It is the share of flagged items the reviewer said were fine. In the sample, the small-length-deviation rule had 4 false alarms out of 7. That tells me this rule creates most of the unnecessary review work, so its threshold is the first one to tune.

**4. How do you know the tool is correct?**
Two ways: unit tests with hand-calculated values, and a synthetic dataset where I know exactly which rows are broken. I am careful about what that proves. Detecting defects I injected myself shows the code works as designed; it does not measure accuracy on real schedules. For that I would need real, independently checked data.

**5. How would you scale this to a team of reviewers?**
Assign queue items to reviewers, have a share of items reviewed twice to measure agreement, add an adjudicator for disagreements, and track throughput and accuracy per reviewer. The decision table already stores reviewer name and time, so those reports can be built on it.

## Terms to know

- **Human-in-the-loop (HITL)**: a process where a person reviews or corrects part of what the automation produces.
- **Audit trail**: a record of who decided what and when, never overwritten.
- **Ground truth**: the known correct answer used to measure a system.
