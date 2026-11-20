import json
import os

import pandas as pd
import pytest

import run
from ops_kpi import dashboard, generate, kpis, loaders

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
MON = pd.Timestamp("2026-09-07")          # a Monday
TARGETS = loaders.load_targets(os.path.join(DATA, "kpi_targets.json"))


def tasks(rows):
    """rows: (id, queue, created, due, completed, minutes, qa, reworked)"""
    frame = pd.DataFrame(rows, columns=["task_id", "queue", "created_at", "due_at", "completed_at",
                                        "handling_minutes", "qa_result", "reworked"])
    for col in ("created_at", "due_at", "completed_at"):
        frame[col] = pd.to_datetime(frame[col])
    frame["annotator_id"] = "a1"
    frame["handling_minutes"] = frame["handling_minutes"].astype(float)
    return frame


def staff(rows):
    frame = pd.DataFrame(rows, columns=["week_start", "annotator_id", "queue", "paid_hours", "hourly_cost"])
    frame["week_start"] = pd.to_datetime(frame["week_start"])
    frame["cost"] = frame["paid_hours"] * frame["hourly_cost"]
    return frame


# Five tasks created in week 1. Four finished in week 1, one still open at the end of week 2.
SMALL = tasks([
    ("t1", "q", "2026-09-07 08:00", "2026-09-08 08:00", "2026-09-07 18:00", 30, "pass", False),  # 10 h, on time
    ("t2", "q", "2026-09-07 08:00", "2026-09-08 08:00", "2026-09-08 04:00", 30, "fail", True),   # 20 h, on time
    ("t3", "q", "2026-09-08 08:00", "2026-09-09 08:00", "2026-09-09 14:00", 60, "", False),      # 30 h, late
    ("t4", "q", "2026-09-09 08:00", "2026-09-10 08:00", "2026-09-11 00:00", 60, "pass", False),  # 40 h, late
    ("t5", "q", "2026-09-11 08:00", "2026-09-12 08:00", None, None, "", False),                  # open, overdue
])
SMALL_STAFF = staff([("2026-09-07", "a1", "q", 6.0, 20.0), ("2026-09-14", "a1", "q", 6.0, 20.0)])


def test_week_start_is_monday():
    assert kpis.week_start("2026-09-09 13:00") == MON
    assert kpis.week_start("2026-09-13 23:59") == MON
    assert kpis.week_start("2026-09-14 00:00") == MON + pd.Timedelta(days=7)


def test_week_kpis_hand_calculated():
    k = kpis.week_kpis(SMALL, SMALL_STAFF, MON)
    assert (k["arrivals"], k["completed"], k["backlog_end"], k["overdue_open_end"]) == (5, 4, 1, 1)
    assert k["sla_compliance"] == pytest.approx(0.5)             # 2 of 4 on time
    assert k["turnaround_median_h"] == pytest.approx(25)         # median of 10, 20, 30, 40
    assert k["turnaround_p90_h"] == pytest.approx(37)            # 90th percentile, linear
    assert k["qa_sampled"] == 3
    assert k["qa_pass_rate"] == pytest.approx(2 / 3)
    assert k["rework_rate"] == pytest.approx(0.25)
    assert k["handling_minutes_mean"] == pytest.approx(45)
    assert k["paid_hours"] == 6 and k["labour_cost"] == 120
    assert k["utilisation"] == pytest.approx(0.5)                # 3 h handled / 6 h paid
    assert k["cost_per_task"] == pytest.approx(30)
    assert k["tasks_per_paid_hour"] == pytest.approx(4 / 6)


def test_empty_week_gives_none_not_zero_or_error():
    k = kpis.week_kpis(SMALL, SMALL_STAFF, MON + pd.Timedelta(days=7))
    assert (k["arrivals"], k["completed"], k["backlog_end"]) == (0, 0, 1)
    for name in ("sla_compliance", "qa_pass_rate", "rework_rate", "cost_per_task", "turnaround_p90_h"):
        assert k[name] is None
    assert k["utilisation"] == 0
    no_staff = kpis.week_kpis(SMALL, SMALL_STAFF.iloc[0:0], MON)
    assert no_staff["utilisation"] is None and no_staff["tasks_per_paid_hour"] is None


def test_a_task_finished_exactly_at_week_end_belongs_to_the_next_week():
    t = tasks([("t1", "q", "2026-09-07 08:00", "2026-09-20 08:00", "2026-09-14 00:00", 10, "", False)])
    assert kpis.week_kpis(t, SMALL_STAFF, MON)["completed"] == 0
    assert kpis.week_kpis(t, SMALL_STAFF, MON)["backlog_end"] == 1
    assert kpis.week_kpis(t, SMALL_STAFF, MON + pd.Timedelta(days=7))["completed"] == 1


def test_backlog_is_arrivals_minus_completions_over_time(tmp_path):
    t, w = generate.generate(seed=1)                     # a different seed from the committed sample
    t.to_csv(tmp_path / "t.csv", index=False)
    w.to_csv(tmp_path / "w.csv", index=False)
    weekly = kpis.weekly_table(loaders.load_tasks(tmp_path / "t.csv")[0], loaders.load_workforce(tmp_path / "w.csv"))
    overall = weekly[weekly["queue"] == "ALL"]
    assert list(overall["backlog_end"]) == list(overall["arrivals"].cumsum() - overall["completed"].cumsum())


def test_weekly_table_has_all_row_and_queue_rows_that_add_up():
    two = pd.concat([SMALL, SMALL.assign(queue="r", task_id=SMALL["task_id"] + "r")])
    weekly = kpis.weekly_table(two, SMALL_STAFF)
    first = weekly[weekly["week_start"] == MON].set_index("queue")
    assert set(first.index) == {"ALL", "q", "r"}
    assert first.loc["ALL", "completed"] == first.loc["q", "completed"] + first.loc["r", "completed"] == 8
    assert first.loc["r", "paid_hours"] == 0


def test_status_levels_both_directions():
    higher = {"direction": "higher", "target": 0.95, "warn": 0.90}
    assert [kpis.status(v, higher) for v in (0.95, 0.949, 0.90, 0.899)] == ["green", "amber", "amber", "red"]
    lower = {"direction": "lower", "target": 48, "warn": 72}
    assert [kpis.status(v, lower) for v in (48, 60, 72, 72.1)] == ["green", "amber", "amber", "red"]
    assert kpis.status(None, lower) == "no data"
    assert kpis.status(float("nan"), lower) == "no data"


def test_scorecard_change_and_per_queue_target():
    weekly = kpis.weekly_table(SMALL, SMALL_STAFF, weeks=[MON, MON + pd.Timedelta(days=7)])
    targets = {"cost_per_task": {"label": "Cost", "format": "money", "direction": "lower",
                                 "target": 10, "warn": 20, "by_queue": {"q": {"target": 30, "warn": 40}}},
               "backlog_end": {"label": "Backlog", "format": "number", "direction": "lower",
                               "target": 0, "warn": 5}}
    week1 = weekly[weekly["week_start"] == MON]
    assert kpis.scorecard(week1, targets)[0]["status"] == "red"             # 30 against the general 10 / 20
    assert kpis.scorecard(week1, targets, "q")[0]["status"] == "green"      # 30 against the queue's own 30
    assert kpis.scorecard(week1, targets)[0]["change"] is None              # no earlier week
    backlog = kpis.scorecard(weekly, targets)[1]
    assert (backlog["value"], backlog["previous"], backlog["change"], backlog["status"]) == (1, 1, 0, "amber")
    with pytest.raises(ValueError, match="unknown KPI"):
        kpis.scorecard(weekly, {"nonsense": targets["backlog_end"]})


def weekly_frame(rows):
    """rows: (arrivals, completed, backlog_end, paid_hours) per week, one queue."""
    frame = pd.DataFrame(rows, columns=["arrivals", "completed", "backlog_end", "paid_hours"])
    frame["week_start"] = pd.date_range(MON, periods=len(rows), freq="7D")
    frame["queue"] = "ALL"
    return frame


def test_forecast_shrinking_backlog():
    f = kpis.forecast(weekly_frame([(999, 1, 0, 1), (100, 120, 80, 40), (100, 130, 50, 40), (100, 110, 40, 40)]))
    assert f["weeks_used"] == 3                           # the first week is outside the lookback
    assert (f["avg_arrivals"], f["avg_completed"], f["net_per_week"]) == (100, 120, 20)
    assert f["trend"] == "shrinking"
    assert f["weeks_to_clear"] == pytest.approx(2.0)      # 40 / 20
    assert f["throughput_gap"] == 0                       # needs 110 a week, already doing 120
    assert f["extra_paid_hours_per_week"] == 0


def test_forecast_growing_backlog_and_extra_hours():
    f = kpis.forecast(weekly_frame([(150, 100, 50, 50), (150, 100, 100, 50), (150, 100, 150, 50)]),
                      clear_in_weeks=5)
    assert f["trend"] == "growing" and f["weeks_to_clear"] is None
    assert f["throughput_needed"] == pytest.approx(180)   # 150 arrivals + 150 backlog / 5 weeks
    assert f["throughput_gap"] == pytest.approx(80)
    assert f["tasks_per_paid_hour"] == pytest.approx(2)
    assert f["extra_paid_hours_per_week"] == pytest.approx(40)


def test_forecast_flat_and_empty_backlog():
    assert kpis.forecast(weekly_frame([(100, 100, 30, 10)] * 3))["trend"] == "flat"
    done = kpis.forecast(weekly_frame([(100, 100, 0, 10)] * 3))
    assert (done["trend"], done["weeks_to_clear"]) == ("no backlog", 0)


# ---- loading and validation -----------------------------------------------------

def test_task_problems_are_listed_and_handled():
    clean, issues = loaders.load_tasks(os.path.join(DATA, "invalid", "tasks_with_problems.csv"))
    found = {(i["row"], i["problem"]) for i in issues}
    assert (3, "duplicate task_id") in found
    assert (4, "created_at missing or not a date") in found
    assert (5, "completed before it was created") in found
    assert (6, "due_at missing or not a date") in found
    assert (7, "handling_minutes missing or not positive") in found
    assert (7, "qa_result is not pass, fail or blank") in found
    assert (8, "blank task_id or queue") in found
    assert (9, "completed_at is not a date") in found
    assert list(clean["task_id"]) == ["T1", "T4", "T5", "T8"]
    t5 = clean.set_index("task_id").loc["T5"]
    assert t5["qa_result"] == "" and pd.isna(t5["handling_minutes"])
    k = kpis.week_kpis(clean, loaders.load_workforce(os.path.join(DATA, "invalid", "workforce_demo.csv")), MON)
    assert k["completed"] == 3 and k["backlog_end"] == 1
    assert k["sla_compliance"] == pytest.approx(1.0)      # T4 has no due date, so 2 of 2
    assert k["handling_minutes_mean"] == pytest.approx(4.5)


def test_bad_files_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="missing column"):
        loaders.load_tasks(os.path.join(DATA, "invalid", "tasks_missing_columns.csv"))
    with pytest.raises(ValueError, match="wrong side"):
        loaders.load_targets(os.path.join(DATA, "invalid", "targets_warn_wrong_side.json"))
    bad = tmp_path / "t.json"
    bad.write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        loaders.load_targets(str(bad))
    bad.write_text('{"x": {"label": "X", "format": "pct", "direction": "sideways", "target": 1, "warn": 1}}')
    with pytest.raises(ValueError, match="direction"):
        loaders.load_targets(str(bad))
    wf = tmp_path / "w.csv"
    wf.write_text("week_start,annotator_id,queue,paid_hours,hourly_cost\n2026-09-08,a,q,10,20\n")
    with pytest.raises(ValueError, match="Monday"):
        loaders.load_workforce(str(wf))
    wf.write_text("week_start,annotator_id,queue,paid_hours,hourly_cost\n2026-09-07,a,q,ten,20\n")
    with pytest.raises(ValueError, match="row"):
        loaders.load_workforce(str(wf))


# ---- dashboard ------------------------------------------------------------------

def test_formatting():
    assert dashboard.fmt(0.9512, "pct") == "95.1%"
    assert dashboard.fmt(None, "pct") == "n/a"
    assert dashboard.fmt(1234.0, "number") == "1,234"
    assert dashboard.fmt(3.2, "money") == "3.20"
    card = {"change": -0.02, "format": "pct", "direction": "higher"}
    assert dashboard.fmt_change(card) == "-2.0 pts vs previous week (worse)"
    assert "better" in dashboard.fmt_change({"change": -5.0, "format": "hours", "direction": "lower"})
    assert dashboard.fmt_change({"change": None, "format": "pct", "direction": "higher"}) == "no previous week"


def test_dashboard_is_self_contained_and_escapes_text():
    two = pd.concat([SMALL.assign(queue="<b>q&a</b>")])
    res = kpis.analyse(two, SMALL_STAFF.assign(queue="<b>q&a</b>"), TARGETS)
    page = dashboard.build(res, TARGETS, [{"row": 2, "problem": "<script>x</script>", "action": "row dropped"}],
                           "file.csv")
    assert page.startswith("<!doctype html>")
    assert "<svg" in page and "<script" not in page
    assert "http://" not in page and "https://" not in page
    assert "&lt;b&gt;q&amp;a&lt;/b&gt;" in page
    assert "Synthetic sample data" not in page
    assert "No data" in page or "Off target" in page


def test_line_chart_handles_gaps_and_no_data():
    assert "No data" in dashboard.line_chart(["a", "b"], [("s", [None, None])])
    svg = dashboard.line_chart(["a", "b", "c"], [("s", [0.9, None, 0.8])], "pct", target=0.95)
    assert svg.count("<circle") == 2 and "target" in svg
    assert "<svg" in dashboard.line_chart(["a"], [("s", [5])])


# ---- sample data and command line -----------------------------------------------

def test_committed_sample_equals_generator_output(tmp_path):
    t, w = generate.generate()
    t.to_csv(tmp_path / "tasks.csv", index=False)
    w.to_csv(tmp_path / "workforce.csv", index=False)
    for name in ("tasks.csv", "workforce.csv"):
        with open(tmp_path / name) as new, open(os.path.join(DATA, name)) as old:
            assert new.read() == old.read(), name


@pytest.fixture(scope="module")
def sample():
    t, issues = loaders.load_tasks(os.path.join(DATA, "tasks.csv"))
    assert issues == []
    return kpis.analyse(t, loaders.load_workforce(os.path.join(DATA, "workforce.csv")), TARGETS)


def test_planted_problems_show_up_in_the_sample(sample):
    weekly = sample["weekly"]
    def row(queue, week):
        start = pd.Timestamp("2026-08-31") + pd.Timedelta(days=7 * (week - 1))
        return weekly[(weekly["queue"] == queue) & (weekly["week_start"] == start)].iloc[0]
    # 1. absence in week 3: backlog appears, then clears
    assert row("text_classification", 2)["backlog_end"] == 0
    assert row("text_classification", 3)["backlog_end"] > 150
    assert row("text_classification", 3)["paid_hours"] == 75
    assert row("text_classification", 8)["backlog_end"] == 0
    # 2. QA dip in weeks 5-6
    assert row("llm_response_rating", 5)["qa_pass_rate"] < 0.88
    assert row("llm_response_rating", 6)["qa_pass_rate"] < 0.88
    assert row("llm_response_rating", 3)["qa_pass_rate"] > 0.90
    # 3. arrival surge from week 6: backlog grows every week
    growth = [row("image_bounding_box", w)["backlog_end"] for w in (5, 6, 7, 8)]
    assert growth[0] == 0 and growth[1] < growth[2] < growth[3]
    status = {c["kpi"]: c["status"] for c in sample["queue_scorecards"]["image_bounding_box"]}
    assert status["sla_compliance"] == "red"
    outlook = {f["queue"]: f for f in sample["forecasts"]}
    assert outlook["image_bounding_box"]["trend"] == "growing"
    assert outlook["image_bounding_box"]["extra_paid_hours_per_week"] > 20
    assert outlook["text_classification"]["trend"] == "no backlog"
    assert "sla_compliance" in sample["red_kpis"]


def test_cli_exit_codes_and_files(tmp_path, capsys):
    out = str(tmp_path / "out")
    assert run.main(["report", "--out-dir", out]) == 1               # sample has KPIs off target
    for name in ("dashboard.html", "weekly_kpis.csv", "summary.json", "issues.csv"):
        assert os.path.exists(os.path.join(out, name)), name
    with open(os.path.join(out, "summary.json")) as handle:
        summary = json.load(handle)
    assert summary["latest_week_start"] == "2026-10-19"
    assert len(summary["forecasts"]) == 4
    assert len(pd.read_csv(os.path.join(out, "weekly_kpis.csv"))) == 8 * 4
    with open(os.path.join(out, "dashboard.html")) as handle:
        assert "Synthetic sample data" in handle.read()
    inv = os.path.join(DATA, "invalid")
    easy = tmp_path / "easy.json"
    easy.write_text('{"sla_compliance": {"label": "SLA", "format": "pct", "direction": "higher", '
                    '"target": 0.5, "warn": 0.4}}')
    assert run.main(["report", "--tasks", os.path.join(inv, "tasks_with_problems.csv"),
                     "--workforce", os.path.join(inv, "workforce_demo.csv"),
                     "--targets", str(easy), "--out-dir", out]) == 0
    assert len(pd.read_csv(os.path.join(out, "issues.csv"))) == 8
    assert run.main(["report", "--tasks", os.path.join(inv, "tasks_missing_columns.csv"), "--out-dir", out]) == 2
    assert run.main(["report", "--tasks", "nope.csv", "--out-dir", out]) == 2
    assert run.main(["report", "--lookback", "0", "--out-dir", out]) == 2
    assert "ERROR" in capsys.readouterr().err
