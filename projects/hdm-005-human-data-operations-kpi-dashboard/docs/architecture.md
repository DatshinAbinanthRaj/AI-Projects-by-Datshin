# Architecture

```
data/tasks.csv        data/workforce.csv        data/kpi_targets.json
      |                      |                          |
      v                      v                          v
src/ops_kpi/loaders.py
  load_tasks()      clean rows + list of problems (row, problem, action)
  load_workforce()  paid hours and cost per person per week
  load_targets()    target, warning level and direction per KPI
      |
      v
src/ops_kpi/kpis.py                  all numbers are calculated here
  week_kpis()       16 figures for one week and one set of tasks
  weekly_table()    one row per week for "ALL" and for each queue
  status()          green / amber / red / no data
  scorecard()       latest week against targets, with change from the week before
  forecast()        backlog trend, weeks to clear, extra paid hours needed
  analyse()         runs everything, returns one dictionary
      |
      +--> src/ops_kpi/dashboard.py   build(): one HTML page, inline CSS and SVG
      +--> run.py                     dashboard.html, weekly_kpis.csv, summary.json,
                                      issues.csv, console summary, exit code
```

## Design choices

- **One place for calculations.** The dashboard, the CSV and the JSON all read from the same `analyse()` result, so they cannot disagree, and the numbers can be tested without opening a browser.
- **The same function for the total and for each queue.** `week_kpis()` is given a filtered set of tasks; there is no second formula for queue-level figures.
- **Targets are data.** Changing a target, or giving one queue its own target, means editing a JSON file. The loader rejects a warning level that sits on the wrong side of the target.
- **"No data" is a status.** A week with no completed tasks has no SLA figure. It is shown as `n/a`, never as 0% or 100%.
- **Clear week boundary.** A task completed at exactly Monday 00:00 belongs to the new week. This is tested.
- **A static file, not a web application.** The dashboard is one HTML file with no scripts and no external resources. It can be emailed, archived per week, or opened offline. Project 002 in this portfolio is the interactive (Streamlit) alternative.
- **Status is written as words as well as colour**, so the page works for colour-blind readers and in print.
- **The outlook is deliberately simple** and says so on the page. A manager can check it with a calculator.
- **Validation never hides data loss.** Each dropped or repaired row is listed with its spreadsheet row number.

## Files

| Path | Purpose |
|---|---|
| `run.py` | command line: `generate`, `report` |
| `src/ops_kpi/loaders.py` | reading and validation |
| `src/ops_kpi/kpis.py` | KPI, status and outlook calculations |
| `src/ops_kpi/dashboard.py` | HTML page and SVG charts |
| `src/ops_kpi/generate.py` | day-by-day queue simulation for the sample data |
| `tests/test_ops_kpi.py` | 19 tests |
| `data/` | synthetic sample, targets, invalid samples, sample output |
