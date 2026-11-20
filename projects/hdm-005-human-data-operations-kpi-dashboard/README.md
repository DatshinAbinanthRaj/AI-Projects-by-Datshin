# HDM-005: Human Data Operations KPI Dashboard

A command-line tool that turns a task log and a workforce file into a one-page weekly KPI dashboard for a data labelling operation: service level, quality, speed, cost, backlog, and a simple outlook that says whether the backlog is clearing and how many extra paid hours would clear it.

> Prototype on **synthetic data**. A red status is a prompt to investigate, not a judgement about a team.

## Business problem

A human data operation (annotation, LLM response rating, review work) is run on a handful of numbers: are we delivering on time, is the quality holding, what does a task cost, and is the backlog under control. In practice these numbers sit in different exports, are calculated differently by different people, and reach the manager too late. Two questions are especially hard to answer quickly:

- **Which queue is the problem?** An overall figure can look acceptable while one queue is failing.
- **What do I need to ask for?** "The backlog is growing" is an observation. "We need about 40 more paid hours a week on this queue to clear it in four weeks" is a request a manager can act on.

## Solution

1. Read a **task log** (one row per task) and a **workforce file** (paid hours and hourly cost per person per week), and list every bad row.
2. Calculate 16 weekly figures for the whole operation and for each queue.
3. Compare the latest week with **targets kept in a JSON file**, giving each KPI a status: on target, watch, or off target. A queue can have its own target where one target for all would be unfair (for example cost per task).
4. Produce a **backlog outlook** from the average of the last few weeks.
5. Write a single **HTML dashboard** (charts drawn as inline SVG, no scripts, no internet needed), plus CSV and JSON for further use.

## Features

- KPIs per week and per queue: arrivals, completions, backlog, open tasks past due, SLA compliance, median and 90th-percentile turnaround, QA pass rate, rework rate, handling time, utilisation, labour cost per task, tasks per paid hour
- Targets as data: target level, warning level, direction (higher or lower is better), optional per-queue override
- Status for each KPI, with the change from the previous week marked better or worse
- Backlog outlook: trend, weeks to clear, extra throughput and extra paid hours needed to clear in a chosen number of weeks
- Self-contained HTML dashboard that works offline, on a phone, and in light or dark mode
- Input validation with a list of every dropped or repaired row
- Exit code for automation: `0` nothing off target, `1` at least one KPI off target, `2` input could not be used
- Synthetic eight-week data generator with three planted problems

## Architecture

```
tasks.csv   workforce.csv   kpi_targets.json
    \            |              /
     loaders.py  (clean, validate, list problems)
                 |
     kpis.py     weekly_table -> scorecard -> forecast
                 |
   +-------------+--------------+
dashboard.py (HTML + SVG)    run.py (CSV, JSON, console summary, exit code)
```

See [docs/architecture.md](docs/architecture.md) and [docs/project_explanation.md](docs/project_explanation.md).

## Technology

Python 3.10+, pandas (date handling and aggregation), standard library (HTML, SVG, JSON, argparse), pytest.

## Install and run

```bash
pip install -r requirements.txt

python run.py report --out-dir out            # sample data -> out/dashboard.html
python run.py report --tasks T.csv --workforce W.csv --targets K.json --out-dir out
python run.py report --lookback 4 --clear-in-weeks 6 --out-dir out
python run.py report --tasks data/invalid/tasks_with_problems.csv \
                     --workforce data/invalid/workforce_demo.csv --out-dir out
python run.py generate                        # rebuild the sample data (seed 5)
python -m pytest
```

Open `out/dashboard.html` in any browser.

## Input

`tasks.csv`

| Column | Meaning |
|---|---|
| `task_id` | unique task |
| `queue` | work stream |
| `created_at` | when the task entered the queue |
| `due_at` | deadline under the service level |
| `completed_at` | when it was finished; blank if still open |
| `annotator_id` | who did it |
| `handling_minutes` | time spent on the task |
| `qa_result` | `pass`, `fail`, or blank if not sampled for QA |
| `reworked` | 1 if the task had to be redone |

`workforce.csv`: `week_start` (a Monday), `annotator_id`, `queue`, `paid_hours`, `hourly_cost`.

`kpi_targets.json`: one entry per KPI with `label`, `format`, `direction`, `target`, `warn`, and optional `by_queue`.

## How each KPI is calculated

A week runs from Monday 00:00 to the next Monday 00:00.

| KPI | Calculation |
|---|---|
| Arrivals / Completed | tasks created / completed in the week |
| Backlog | created before the week ended and not completed by then |
| Open tasks past due | backlog tasks whose deadline is before the week ended |
| SLA compliance | of tasks completed in the week, share completed on or before the deadline |
| Turnaround | completed time minus created time, in hours (median and 90th percentile) |
| QA pass rate | of completed tasks sampled for QA, share that passed |
| Rework rate | share of completed tasks that were redone |
| Utilisation | handling hours divided by paid hours |
| Labour cost per task | paid hours x hourly cost, divided by tasks completed |
| Weeks to clear | backlog divided by (average completed minus average arrivals), when that is positive |
| Extra paid hours | (average arrivals + backlog / weeks allowed - average completed) divided by tasks per paid hour |

## Sample data

`data/tasks.csv` (15,449 tasks) and `data/workforce.csv` are synthetic, produced by `src/ops_kpi/generate.py` with seed 5. Three queues are simulated day by day for eight weeks: tasks arrive on weekdays, each team has a daily capacity, and the oldest task is worked first. Three problems are planted on purpose:

| Planted problem | Where |
|---|---|
| One annotator absent for a week | `text_classification`, week 3 (14 Sep) |
| QA pass rate falls to about 80% and rework doubles | `llm_response_rating`, weeks 5 and 6 |
| Arrivals 45% higher with no extra staff | `image_bounding_box`, weeks 6 to 8 |

`data/invalid/` holds a nine-row task file with eight input problems, a file with missing columns, and a targets file with the warning level on the wrong side.

## Example output

`data/sample_output/dashboard.html` is the dashboard for the sample data. Latest week (starting 19 Oct 2026), all queues:

| KPI | Value | Target | Status |
|---|---|---|---|
| SLA compliance | 85.8% | at least 95% | Off target |
| QA pass rate | 93.2% | at least 92% | On target |
| Rework rate | 5.7% | at most 6% | On target |
| Turnaround, 90th percentile | 93.4 h | at most 36 h | Off target |
| Utilisation | 73.1% | at least 65% | On target |
| Labour cost per task | 3.20 | at most 3.60 | On target |
| Open tasks past due | 228 | at most 25 | Off target |

Backlog outlook:

| Queue | Backlog | Arrivals / week | Completed / week | Trend | Extra paid hours / week to clear in 4 weeks |
|---|---|---|---|---|---|
| image_bounding_box | 362 | 721 | 601 | growing | 40 |
| llm_response_rating | 0 | 391 | 391 | no backlog | 0 |
| text_classification | 0 | 963 | 972 | no backlog | 0 |

## Validation

- **19 automated tests**, all passing: every KPI against a five-task case worked out by hand, week boundaries, empty weeks, status levels in both directions, per-queue targets, the three outlook cases (shrinking, growing, flat), each validation rule, HTML escaping, the command line and its exit codes, and a check that the committed sample equals the generator output.
- A consistency check on a second generated dataset: backlog at the end of each week equals total arrivals minus total completions up to that point.
- The dashboard was opened in a headless browser at desktop width (light) and phone width (dark): no console errors and no sideways scrolling of the page. This was a one-off visual check, not an automated UI test.

What the sample run shows, and what it does not:

- All three planted problems are visible: the week-3 backlog on `text_classification` that clears by week 6, the QA dip on `llm_response_rating` (77.3% and 85.9%), and the growing backlog on `image_bounding_box` with SLA compliance at 53.9%.
- The overall view hides the cause. Overall SLA compliance is 85.8%; two queues are at 100% and one is at 53.9%.
- In the absence week, labour cost per task on `text_classification` went **down** (1.68 against about 1.86) and utilisation went **up**, while a backlog of 265 tasks built up. Cost and utilisation looked better in the week service got worse. This is why the dashboard shows them side by side.
- The QA dip is two weeks in the past, so the latest-week tiles do not show it; only the trend chart does. A dashboard that shows one week only would have missed it.
- These results come from a simulation built to contain these problems. They show the calculations and the presentation work. They say nothing about how real operations behave.

## Business applications

Weekly operations review for an annotation or evaluation team; vendor performance review against a service level; staffing requests backed by a number; early warning when one queue starts to slip; a scheduled job that fails loudly when a KPI goes off target.

## Skills demonstrated

Operations KPI definition, service-level and backlog measurement, cost per unit and utilisation, targets as configuration, traffic-light status reporting, throughput and capacity outlook, queue simulation for test data, data validation, dependency-free HTML and SVG reporting, test-driven metric code.

## Limitations

- The outlook is arithmetic on recent averages. It assumes the coming weeks look like the last ones and gives no range.
- The latest week is treated as complete. Run it after the week has closed.
- Deadlines are compared in calendar hours; there is no working-hours or holiday calendar.
- Cost is labour cost from the workforce file only: no tooling, management or vendor fees.
- A person is assigned to one queue per week in the workforce file; shared staff must be split by hand.
- QA pass rate depends on the sample; no confidence interval is shown here, so a weekly figure from 50 samples moves a lot by chance.
- Rework is a yes/no flag; the time spent on rework is not measured separately.
- No login, no storage, no live refresh: it is a report generator, run on files.

## Future improvements

Confidence intervals on QA pass rate; a range on the outlook; working-hours calendar for deadlines; per-annotator view; comparison of two periods; reading directly from a database.
