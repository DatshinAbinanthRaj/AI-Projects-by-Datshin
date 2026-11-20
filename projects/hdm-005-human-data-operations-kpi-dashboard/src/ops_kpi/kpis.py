"""KPI calculations. Every figure on the dashboard comes from this file.

A week runs from Monday 00:00 to the next Monday 00:00.
"""
import math

import pandas as pd

WEEK = pd.Timedelta(days=7)
KPI_COLUMNS = ["arrivals", "completed", "backlog_end", "overdue_open_end", "sla_compliance",
               "turnaround_median_h", "turnaround_p90_h", "qa_sampled", "qa_pass_rate",
               "rework_rate", "handling_minutes_mean", "paid_hours", "labour_cost",
               "utilisation", "cost_per_task", "tasks_per_paid_hour"]


def week_start(ts):
    ts = pd.Timestamp(ts).normalize()
    return ts - pd.Timedelta(days=ts.weekday())


def week_list(tasks):
    """Every Monday from the first task created to the last recorded activity."""
    first = week_start(tasks["created_at"].min())
    last = week_start(max(tasks["created_at"].max(), tasks["completed_at"].max()))
    return list(pd.date_range(first, last, freq="7D"))


def _ratio(top, bottom):
    return top / bottom if bottom else None


def _clean(value):
    """Turn NaN into None and numpy numbers into plain Python numbers."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
        if isinstance(value, float) and math.isnan(value):
            return None
    return value


def week_kpis(tasks, workforce, start):
    """KPIs for one week, for whatever tasks and workforce rows are passed in."""
    end = start + WEEK
    created = tasks[(tasks["created_at"] >= start) & (tasks["created_at"] < end)]
    done = tasks[(tasks["completed_at"] >= start) & (tasks["completed_at"] < end)]
    open_at_end = tasks[(tasks["created_at"] < end)
                        & (tasks["completed_at"].isna() | (tasks["completed_at"] >= end))]
    with_due = done[done["due_at"].notna()]
    sampled = done[done["qa_result"] != ""]
    turnaround = (done["completed_at"] - done["created_at"]).dt.total_seconds() / 3600
    staff = workforce[workforce["week_start"] == start]
    paid = float(staff["paid_hours"].sum())
    cost = float(staff["cost"].sum())
    handled_hours = float(done["handling_minutes"].sum()) / 60
    out = {
        "arrivals": len(created),
        "completed": len(done),
        "backlog_end": len(open_at_end),
        "overdue_open_end": int((open_at_end["due_at"] < end).sum()),
        "sla_compliance": _ratio(int((with_due["completed_at"] <= with_due["due_at"]).sum()), len(with_due)),
        "turnaround_median_h": turnaround.median() if len(done) else None,
        "turnaround_p90_h": turnaround.quantile(0.9) if len(done) else None,
        "qa_sampled": len(sampled),
        "qa_pass_rate": _ratio(int((sampled["qa_result"] == "pass").sum()), len(sampled)),
        "rework_rate": _ratio(int(done["reworked"].sum()), len(done)),
        "handling_minutes_mean": done["handling_minutes"].mean() if len(done) else None,
        "paid_hours": paid,
        "labour_cost": cost,
        "utilisation": _ratio(handled_hours, paid),
        "cost_per_task": _ratio(cost, len(done)),
        "tasks_per_paid_hour": _ratio(len(done), paid),
    }
    return {k: _clean(v) for k, v in out.items()}


def weekly_table(tasks, workforce, weeks=None):
    """One row per week and queue, plus an 'ALL' row per week."""
    weeks = weeks or week_list(tasks)
    rows = []
    for start in weeks:
        rows.append({"week_start": start, "queue": "ALL", **week_kpis(tasks, workforce, start)})
        for queue in sorted(tasks["queue"].unique()):
            rows.append({"week_start": start, "queue": queue,
                         **week_kpis(tasks[tasks["queue"] == queue],
                                     workforce[workforce["queue"] == queue], start)})
    return pd.DataFrame(rows).astype({c: "object" for c in KPI_COLUMNS})


def status(value, target):
    """green / amber / red for one KPI value against its target, or 'no data'."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "no data"
    if target["direction"] == "higher":
        return "green" if value >= target["target"] else "amber" if value >= target["warn"] else "red"
    return "green" if value <= target["target"] else "amber" if value <= target["warn"] else "red"


def scorecard(weekly, targets, queue="ALL"):
    """Latest week against targets, with the change from the week before."""
    rows = weekly[weekly["queue"] == queue].sort_values("week_start")
    latest = rows.iloc[-1]
    previous = rows.iloc[-2] if len(rows) > 1 else None
    cards = []
    for name, target in targets.items():
        if name not in rows.columns:
            raise ValueError(f"targets file names an unknown KPI: '{name}'")
        target = {**target, **target.get("by_queue", {}).get(queue, {})}
        value = _clean(latest[name])
        before = _clean(previous[name]) if previous is not None else None
        cards.append({
            "kpi": name, "label": target["label"], "format": target["format"],
            "direction": target["direction"], "value": value, "target": target["target"],
            "warn": target["warn"], "status": status(value, target), "previous": before,
            "change": None if value is None or before is None else value - before,
        })
    return cards


def forecast(weekly, queue="ALL", lookback=3, clear_in_weeks=4):
    """Simple backlog outlook from the average of the last `lookback` weeks.

    weeks_to_clear   backlog / (completed - arrivals); None when the backlog is not shrinking
    extra_paid_hours paid hours per week to add so the backlog is cleared in
                     `clear_in_weeks` weeks at the current tasks-per-paid-hour rate
    """
    rows = weekly[weekly["queue"] == queue].sort_values("week_start").tail(lookback)
    completed = float(rows["completed"].mean())
    arrivals = float(rows["arrivals"].mean())
    backlog = int(rows.iloc[-1]["backlog_end"])
    paid = float(rows["paid_hours"].sum())
    rate = _ratio(float(rows["completed"].sum()), paid)
    net = completed - arrivals
    needed = arrivals + backlog / clear_in_weeks
    gap = max(0.0, needed - completed)
    if backlog == 0:
        trend, weeks_to_clear = "no backlog", 0.0
    elif net > 0:
        trend, weeks_to_clear = "shrinking", backlog / net
    else:
        trend, weeks_to_clear = ("growing" if net < 0 else "flat"), None
    return {
        "queue": queue, "weeks_used": len(rows), "backlog": backlog,
        "avg_arrivals": arrivals, "avg_completed": completed, "net_per_week": net,
        "trend": trend, "weeks_to_clear": weeks_to_clear,
        "clear_in_weeks": clear_in_weeks, "throughput_needed": needed, "throughput_gap": gap,
        "tasks_per_paid_hour": rate,
        "extra_paid_hours_per_week": gap / rate if rate else None,
    }


def analyse(tasks, workforce, targets, lookback=3, clear_in_weeks=4):
    weekly = weekly_table(tasks, workforce)
    queues = sorted(tasks["queue"].unique())
    cards = scorecard(weekly, targets)
    return {
        "weekly": weekly,
        "latest_week": weekly["week_start"].max(),
        "scorecard": cards,
        "queue_scorecards": {q: scorecard(weekly, targets, q) for q in queues},
        "forecasts": [forecast(weekly, q, lookback, clear_in_weeks) for q in ["ALL"] + queues],
        "red_kpis": [c["kpi"] for c in cards if c["status"] == "red"],
    }
