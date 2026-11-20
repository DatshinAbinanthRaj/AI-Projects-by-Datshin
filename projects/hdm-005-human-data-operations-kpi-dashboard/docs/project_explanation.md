# Project explanation

## What it is

A report generator for the person who runs a data labelling or AI evaluation team. It reads two files that most operations already have, a list of tasks and a list of paid hours, and produces a one-page weekly dashboard.

## Why it matters

AI companies buy or run large amounts of human work: labelling images, classifying text, rating model answers. That work is managed like any other production line. The manager has to keep four things in balance:

- **Service:** is the work delivered by the agreed deadline?
- **Quality:** does the work pass quality checks?
- **Cost:** what does each finished task cost?
- **Flow:** is work arriving faster than it is being finished?

Improving one often harms another. Pushing people to work faster lowers cost per task and can lower quality. Losing a team member lowers total cost that week and builds a backlog. A dashboard is useful when it shows these together, so a good number in one place cannot hide a bad one elsewhere.

## Key terms

- **Queue:** a stream of similar tasks, for example "image bounding boxes".
- **Throughput:** tasks completed per week.
- **Backlog:** tasks that have arrived and are not yet finished.
- **SLA (service level agreement):** the promised deadline, for example "within 48 hours". SLA compliance is the share of tasks finished on time.
- **Turnaround:** time from a task arriving to it being finished. The **90th percentile** is the time within which 90% of tasks are finished; it shows the slow tail that an average hides.
- **QA pass rate:** of the tasks checked by a reviewer, the share found correct.
- **Rework rate:** share of tasks that had to be done again.
- **Utilisation:** hours spent on tasks divided by hours paid. It is never 100%: people have meetings, training and breaks.
- **Status (red, amber, green):** a KPI compared with its target and a warning level.

## How it works, step by step

1. **Read and clean.** Rows with no task ID, an unreadable date, a duplicate ID, or a completion date before the creation date are dropped and listed. Rows with a smaller problem (no deadline, a bad handling time) are kept and left out of the affected figure only.
2. **Split time into weeks**, Monday to Monday.
3. **Calculate each KPI for each week**, once for everything and once per queue.
4. **Compare the latest week with the targets** and give each KPI a status. Show the change from the week before and whether that change is for the better.
5. **Work out the backlog outlook** from the average of the last three weeks.
6. **Write the dashboard**, the tables and a summary file. Return an exit code so a scheduled job can raise an alert.

## A small example of the outlook

A queue has a backlog of 362 tasks. Over the last three weeks it received 721 tasks a week and finished 601. It is falling behind by 120 a week, so the backlog is growing and there is no "weeks to clear".

To clear 362 tasks in four weeks, the team must finish the 721 that arrive plus 362 / 4 = 90.5 more: about 812 a week. That is 211 more than now. The team finishes about 5.3 tasks per paid hour, so 211 / 5.3 = about 40 extra paid hours a week, roughly one more full-time person. These are the actual figures from the sample data.

## What the sample teaches

- **Look by queue.** Overall SLA compliance is 85.8%. Two queues are at 100% and one is at 53.9%.
- **Read cost together with service.** In the week one person was absent, cost per task fell and utilisation rose, and a 265-task backlog appeared.
- **Look at the trend.** The quality dip happened two weeks before the latest week. The tiles for the latest week are fine; the trend chart shows the dip.

## What it does not do

It does not predict the future; the outlook assumes next week looks like recent weeks. It does not measure individual people. It does not replace a discussion with the team about why a number moved.
