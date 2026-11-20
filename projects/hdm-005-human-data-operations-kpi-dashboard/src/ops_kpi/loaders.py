"""Read and clean the task log, the workforce file and the KPI targets."""
import json

import pandas as pd

TASK_COLUMNS = ["task_id", "queue", "created_at", "due_at", "completed_at",
                "annotator_id", "handling_minutes", "qa_result", "reworked"]
WORKFORCE_COLUMNS = ["week_start", "annotator_id", "queue", "paid_hours", "hourly_cost"]
DIRECTIONS = ("higher", "lower")
FORMATS = ("pct", "hours", "money", "number")


def _require(df, columns, name):
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing column(s): {', '.join(missing)}")


def load_tasks(path):
    """Return (clean task table, list of issues). Each issue has row, problem, action."""
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    raw.columns = [c.strip() for c in raw.columns]
    _require(raw, TASK_COLUMNS, path)
    if raw.empty:
        raise ValueError(f"{path}: no rows")
    df = raw[TASK_COLUMNS].apply(lambda col: col.str.strip())
    df["row"] = range(2, len(df) + 2)          # spreadsheet row number
    issues = []

    def drop(mask, problem):
        for row in df.loc[mask, "row"]:
            issues.append({"row": int(row), "problem": problem, "action": "row dropped"})
        return df.loc[~mask].copy()

    def repair(mask, problem, action):
        for row in df.loc[mask, "row"]:
            issues.append({"row": int(row), "problem": problem, "action": action})

    df = drop((df["task_id"] == "") | (df["queue"] == ""), "blank task_id or queue")
    df = drop(df.duplicated("task_id", keep="first"), "duplicate task_id")
    for col in ("created_at", "due_at", "completed_at"):
        df[col + "_raw"] = df[col]
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df = drop(df["created_at"].isna(), "created_at missing or not a date")
    df = drop((df["completed_at_raw"] != "") & df["completed_at"].isna(), "completed_at is not a date")
    df = drop(df["completed_at"] < df["created_at"], "completed before it was created")
    repair(df["due_at"].isna(), "due_at missing or not a date", "kept, left out of SLA figures")

    done = df["completed_at"].notna()
    df["handling_minutes"] = pd.to_numeric(df["handling_minutes"], errors="coerce")
    bad_time = done & (df["handling_minutes"].isna() | (df["handling_minutes"] <= 0))
    repair(bad_time, "handling_minutes missing or not positive", "kept, left out of handling-time figures")
    df.loc[~done | bad_time, "handling_minutes"] = float("nan")

    df["qa_result"] = df["qa_result"].str.lower()
    bad_qa = ~df["qa_result"].isin(["", "pass", "fail"])
    repair(bad_qa, "qa_result is not pass, fail or blank", "kept, treated as not sampled")
    df.loc[bad_qa | ~done, "qa_result"] = ""
    df["reworked"] = df["reworked"].isin(["1", "true", "True", "yes"]) & done

    if df.empty:
        raise ValueError(f"{path}: no usable rows")
    keep = ["task_id", "queue", "created_at", "due_at", "completed_at", "annotator_id",
            "handling_minutes", "qa_result", "reworked"]
    return df[keep].reset_index(drop=True), issues


def load_workforce(path):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    _require(df, WORKFORCE_COLUMNS, path)
    df["week_start"] = pd.to_datetime(df["week_start"], errors="coerce")
    for col in ("paid_hours", "hourly_cost"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    bad = df[["week_start", "paid_hours", "hourly_cost"]].isna().any(axis=1) | (df["paid_hours"] < 0)
    if bad.any():
        rows = ", ".join(str(i + 2) for i in df.index[bad][:5])
        raise ValueError(f"{path}: bad week_start, paid_hours or hourly_cost in row(s) {rows}")
    not_monday = df["week_start"].dt.weekday != 0
    if not_monday.any():
        raise ValueError(f"{path}: week_start must be a Monday (row {df.index[not_monday][0] + 2})")
    df["cost"] = df["paid_hours"] * df["hourly_cost"]
    return df[WORKFORCE_COLUMNS + ["cost"]]


def load_targets(path):
    """Targets file: {kpi: {label, format, direction, target, warn, by_queue (optional)}}.

    by_queue lets one queue have its own target and warn level:
    "by_queue": {"queue_name": {"target": 6.5, "warn": 7.5}}
    """
    with open(path, encoding="utf-8") as handle:
        try:
            targets = json.load(handle)
        except json.JSONDecodeError as err:
            raise ValueError(f"{path}: not valid JSON ({err})") from None
    if not isinstance(targets, dict) or not targets:
        raise ValueError(f"{path}: expected an object with one entry per KPI")
    for name, t in targets.items():
        for key in ("label", "format", "direction", "target", "warn"):
            if key not in t:
                raise ValueError(f"{path}: KPI '{name}' has no '{key}'")
        if t["direction"] not in DIRECTIONS:
            raise ValueError(f"{path}: KPI '{name}' direction must be higher or lower")
        if t["format"] not in FORMATS:
            raise ValueError(f"{path}: KPI '{name}' format must be one of {', '.join(FORMATS)}")
        levels = [("", t)] + [(f" (queue {q})", {**t, **o}) for q, o in t.get("by_queue", {}).items()]
        for where, lv in levels:
            ok = lv["warn"] <= lv["target"] if t["direction"] == "higher" else lv["warn"] >= lv["target"]
            if not ok:
                raise ValueError(f"{path}: KPI '{name}'{where} warn level is on the wrong side of the target")
    return targets
