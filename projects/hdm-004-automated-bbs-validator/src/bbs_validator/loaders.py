"""Read a schedule from CSV (+ optional .meta.json) or from an XLSX workbook.

Both formats end up as the same Schedule object, so the rules never need to
know where the data came from.
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field

REQUIRED_COLUMNS = (
    "bar_mark", "member", "diameter_mm", "no_of_members", "bars_per_member",
    "total_bars", "shape_code", "a_mm", "cut_length_mm",
)
OPTIONAL_COLUMNS = ("b_mm", "c_mm", "d_mm", "e_mm")
ALL_COLUMNS = REQUIRED_COLUMNS[:8] + OPTIONAL_COLUMNS + ("cut_length_mm",)


class ScheduleError(ValueError):
    """The file cannot be read as a schedule at all."""


@dataclass
class Schedule:
    name: str                      # file name, used in every report
    rows: list                     # list of dicts; each has "_line" (line in the file)
    header: dict | None = None     # title-block fields, None if not supplied
    summary: list | None = None    # declared weights: [{"diameter_mm":..,"total_weight_kg":..}]
    notes: list = field(default_factory=list)


def _clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _normalise(headers) -> list:
    return [_clean(h).lower().replace(" ", "_") for h in headers]


def _rows_from_table(headers, records, name) -> list:
    cols = _normalise(headers)
    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing:
        raise ScheduleError(f"{name}: missing column(s): {', '.join(missing)}")
    rows = []
    for line, record in records:
        values = [_clean(v) for v in record]
        if not any(values):
            continue                                    # skip blank lines
        row = {c: "" for c in ALL_COLUMNS}
        for col, value in zip(cols, values):
            if col in row:
                row[col] = value
        row["_line"] = line
        rows.append(row)
    return rows


def _load_csv(path: str) -> Schedule:
    name = os.path.basename(path)
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            table = list(csv.reader(handle))
    except (OSError, UnicodeDecodeError) as exc:
        raise ScheduleError(f"{name}: cannot read file ({exc})") from exc
    if not table:
        raise ScheduleError(f"{name}: file is empty")
    rows = _rows_from_table(table[0], [(i + 2, r) for i, r in enumerate(table[1:])], name)
    schedule = Schedule(name, rows)
    meta_path = os.path.splitext(path)[0] + ".meta.json"
    if os.path.exists(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as handle:
                meta = json.load(handle)
            if not isinstance(meta, dict):
                raise ValueError("top level must be an object")
        except (OSError, ValueError) as exc:
            raise ScheduleError(f"{name}: cannot read {os.path.basename(meta_path)} ({exc})") from exc
        if isinstance(meta.get("header"), dict):
            schedule.header = {str(k).lower(): _clean(v) for k, v in meta["header"].items()}
        if isinstance(meta.get("weight_summary"), list):
            schedule.summary = [s for s in meta["weight_summary"] if isinstance(s, dict)]
    return schedule


def _load_xlsx(path: str) -> Schedule:
    name = os.path.basename(path)
    try:
        import openpyxl
    except ImportError as exc:                           # pragma: no cover
        raise ScheduleError(f"{name}: reading .xlsx needs the openpyxl package") from exc
    try:
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:                             # openpyxl raises several types
        raise ScheduleError(f"{name}: cannot open workbook ({exc})") from exc
    try:
        sheets = {s.title.lower(): s for s in book.worksheets}
        if "schedule" not in sheets:
            raise ScheduleError(f"{name}: workbook has no sheet called 'Schedule'")
        table = list(sheets["schedule"].iter_rows(values_only=True))
        if not table:
            raise ScheduleError(f"{name}: sheet 'Schedule' is empty")
        rows = _rows_from_table(table[0], [(i + 2, r) for i, r in enumerate(table[1:])], name)
        schedule = Schedule(name, rows)
        if "header" in sheets:
            schedule.header = {}
            for record in sheets["header"].iter_rows(min_row=2, values_only=True):
                if record and _clean(record[0]):
                    value = record[1] if len(record) > 1 else ""
                    schedule.header[_clean(record[0]).lower()] = _clean(value)
        if "summary" in sheets:
            schedule.summary = []
            for record in sheets["summary"].iter_rows(min_row=2, values_only=True):
                if record and _clean(record[0]):
                    schedule.summary.append({"diameter_mm": record[0],
                                             "total_weight_kg": record[1] if len(record) > 1 else None})
        return schedule
    finally:
        book.close()


def load_schedule(path: str) -> Schedule:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return _load_csv(path)
    if ext == ".xlsx":
        return _load_xlsx(path)
    raise ScheduleError(f"{os.path.basename(path)}: unsupported file type (use .csv or .xlsx)")


def find_schedules(path: str) -> list:
    """A file path gives that file; a folder gives every .csv and .xlsx in it."""
    if os.path.isdir(path):
        names = sorted(n for n in os.listdir(path)
                       if n.lower().endswith((".csv", ".xlsx")) and not n.startswith("~$"))
        return [os.path.join(path, n) for n in names]
    if os.path.isfile(path):
        return [path]
    raise FileNotFoundError(path)
