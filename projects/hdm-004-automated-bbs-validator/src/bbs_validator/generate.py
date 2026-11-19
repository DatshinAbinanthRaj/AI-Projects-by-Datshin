"""Create the synthetic sample schedules in data/.

Everything here is invented. Clean rows are built from the rule profile, so
they are correct by construction. Defects are then planted on purpose and each
one is written to planted_defects.csv, which the tests use as ground truth.
"""
from __future__ import annotations

import csv
import json
import math
import os
import random

from .loaders import ALL_COLUMNS, Schedule
from .profile import Profile, evaluate
from .rules import computed_weights

SEED = 2026
MEMBER_SETS = {
    "footings": ["Footing F1", "Footing F2", "Footing F3", "Pile cap PC1"],
    "columns": ["Column C1", "Column C2", "Column C3", "Column C4"],
    "beams": ["Beam B1", "Beam B2", "Beam B3", "Beam B4"],
    "slab": ["Slab S1 bottom", "Slab S1 top", "Slab S2 bottom", "Slab S2 top"],
    "walls": ["Wall W1", "Wall W2", "Core wall CW1"],
}
LINK_SHAPES = ("51", "63", "33")
MAIN_SHAPES = ("00", "00", "11", "21", "13", "31", "41", "44")


def _step(value: float, step: int = 5) -> int:
    return int(math.ceil(value / step) * step)


def _dims(rng: random.Random, shape: str, r: float, p: float, d: int) -> dict:
    """Random dimensions that are valid for the shape and bar size."""
    leg = lambda low, high: _step(max(p, rng.randrange(low, high, 25)))      # noqa: E731
    mid = lambda low, high: rng.randrange(low, high, 25)                    # noqa: E731
    loop = _step(2 * (r + d)) + rng.choice((0, 20, 40))
    if shape == "00":
        return {"A": mid(1500, 11000)}
    if shape == "11":
        return {"A": leg(800, 3500), "B": leg(300, 1200)}
    if shape == "13":
        return {"A": leg(600, 1800), "B": loop, "C": leg(600, 1800)}
    if shape == "21":
        return {"A": leg(300, 900), "B": mid(500, 2500), "C": leg(300, 900)}
    if shape == "31":
        return {"A": leg(300, 700), "B": mid(400, 1200), "C": mid(400, 1200), "D": leg(300, 700)}
    if shape == "33":
        return {"A": mid(400, 1200), "B": loop, "C": mid(300, 800)}
    if shape in ("41", "44"):
        return {"A": leg(300, 600), "B": mid(250, 900), "C": mid(250, 900),
                "D": mid(250, 900), "E": leg(300, 600)}
    if shape == "51":
        return {"A": mid(200, 600), "B": mid(300, 800), "C": _step(p) + rng.choice((0, 10, 20))}
    if shape == "63":
        return {"A": mid(200, 500), "B": mid(200, 500), "C": _step(p) + rng.choice((0, 10, 20))}
    raise ValueError(shape)


def cut_length(profile: Profile, shape: str, d: int, dims: dict) -> int:
    values = dict(dims, d=d, r=profile.diameters[d]["r"])
    return int(profile.round_up(evaluate(profile.shapes[shape].formula, values)))


def make_row(profile: Profile, mark: str, member: str, d: int, members: int, per: int,
             shape: str, dims: dict) -> dict:
    row = {c: "" for c in ALL_COLUMNS}
    row.update(bar_mark=mark, member=member, diameter_mm=str(d), no_of_members=str(members),
               bars_per_member=str(per), total_bars=str(members * per), shape_code=shape,
               cut_length_mm=str(cut_length(profile, shape, d, dims)))
    for name, value in dims.items():
        row[f"{name.lower()}_mm"] = str(value)
    return row


def clean_rows(profile: Profile, rng: random.Random, kind: str, count: int) -> list:
    rows = []
    for i in range(count):
        link = i % 4 == 3
        shape = rng.choice(LINK_SHAPES if link else MAIN_SHAPES)
        d = rng.choice((8, 10, 12) if link else (12, 16, 20, 25, 32))
        limits = profile.diameters[d]
        dims = _dims(rng, shape, limits["r"], limits["p"], d)
        rows.append(make_row(profile, f"{i + 1:02d}", rng.choice(MEMBER_SETS[kind]), d,
                             rng.randint(1, 6), rng.randint(2, 24), shape, dims))
    return rows


def _header(drawing: str, revision: str) -> dict:
    return {"project": "Synthetic Demo Building (not a real project)", "drawing_no": drawing,
            "revision": revision, "schedule_date": "2026-11-18",
            "prepared_by": "Detailer A (synthetic)", "checked_by": "Checker B (synthetic)"}


def _declared(profile: Profile, rows: list) -> list:
    """A weight summary that agrees with the rows as they are written."""
    numbered = [dict(r, _line=i + 2) for i, r in enumerate(rows)]
    totals, unusable = computed_weights(Schedule("tmp", numbered), profile)
    return [{"diameter_mm": d, "total_weight_kg": round(w, 1)}
            for d, w in sorted(totals.items()) if d not in unusable]


def _write_csv(path: str, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ALL_COLUMNS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_meta(path: str, header: dict, summary: list) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"synthetic": True, "header": header, "weight_summary": summary}, handle, indent=2)
        handle.write("\n")


def _write_xlsx(path: str, rows: list, header: dict, summary: list) -> None:
    import openpyxl
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Schedule"
    sheet.append(list(ALL_COLUMNS))
    numeric = set(ALL_COLUMNS) - {"bar_mark", "member", "shape_code"}
    for row in rows:
        sheet.append([float(row[c]) if c in numeric and row[c] else row[c] for c in ALL_COLUMNS])
    head = book.create_sheet("Header")
    head.append(["field", "value"])
    for key, value in header.items():
        head.append([key, value])
    summ = book.create_sheet("Summary")
    summ.append(["diameter_mm", "total_weight_kg"])
    for entry in summary:
        summ.append([entry["diameter_mm"], entry["total_weight_kg"]])
    book.save(path)


def generate(profile: Profile, data_dir: str) -> list:
    """Write all sample files and return the list of planted defects."""
    rng = random.Random(SEED)
    sched_dir = os.path.join(data_dir, "schedules")
    bad_dir = os.path.join(data_dir, "invalid")
    os.makedirs(sched_dir, exist_ok=True)
    os.makedirs(bad_dir, exist_ok=True)
    planted: list = []

    def plant(name, index, rows, rule):
        """Record a defect on rows[index] (file line = index + 2); index None = schedule level."""
        line = "" if index is None else index + 2
        mark = "" if index is None else rows[index]["bar_mark"]
        planted.append({"schedule": name, "line": line, "bar_mark": mark, "rule": rule})

    # 1. Clean schedule: should PASS.
    name = "S-101_footings_rev_B.csv"
    rows = clean_rows(profile, rng, "footings", 14)
    _write_csv(os.path.join(sched_dir, name), rows)
    _write_meta(os.path.join(sched_dir, "S-101_footings_rev_B.meta.json"),
                _header("S-101", "B"), _declared(profile, rows))

    # 2. Warnings only: should be REVIEW.
    name = "S-205_columns_rev_A.csv"
    rows = clean_rows(profile, rng, "columns", 12)
    rows[0] = make_row(profile, "01", "Column C1", 25, 4, 8, "00", {"A": 4510})
    rows[0]["cut_length_mm"] = "4510"
    plant(name, 0, rows, "cut_length_not_rounded")
    rows[2] = make_row(profile, "03", "Column C2", 32, 2, 12, "00", {"A": 13500})
    plant(name, 2, rows, "exceeds_max_length")
    rows[4]["shape_code"] = "99"
    plant(name, 4, rows, "unknown_shape_code")
    rows[5] = make_row(profile, "06", "Column C3", 20, 3, 6, "00", {"A": 3200})
    rows[5]["b_mm"] = "300"
    plant(name, 5, rows, "unused_dimension")
    rows[8]["bar_mark"] = "C-09/A"
    plant(name, 8, rows, "bar_mark_format")
    _write_csv(os.path.join(sched_dir, name), rows)
    _write_meta(os.path.join(sched_dir, "S-205_columns_rev_A.meta.json"),
                _header("S-205", "A"), _declared(profile, rows))

    # 3. Row-level errors: should FAIL.
    name = "S-310_beams_rev_C.csv"
    rows = clean_rows(profile, rng, "beams", 16)
    rows[0]["total_bars"] = str(int(rows[0]["total_bars"]) + 4)
    plant(name, 0, rows, "total_bars_mismatch")
    rows[1] = make_row(profile, "02", "Beam B1", 20, 2, 4, "21", {"A": 400, "B": 2400, "C": 400})
    rows[1]["cut_length_mm"] = str(int(rows[1]["cut_length_mm"]) + 300)
    plant(name, 1, rows, "cut_length_mismatch")
    rows[3] = make_row(profile, "04", "Beam B2", 10, 3, 18, "51", {"A": 300, "B": 550, "C": 120})
    rows[3]["c_mm"] = ""
    plant(name, 3, rows, "missing_dimension")
    rows[4] = make_row(profile, "05", "Beam B2", 16, 2, 6, "00", {"A": 5200})
    rows[4]["diameter_mm"] = "14"
    plant(name, 4, rows, "non_standard_diameter")
    rows[5] = make_row(profile, "06", "Beam B3", 25, 2, 4, "11", {"A": 2600, "B": 150})
    plant(name, 5, rows, "leg_too_short")
    rows[6] = make_row(profile, "07", "Beam B3", 20, 1, 6, "13", {"A": 900, "B": 100, "C": 900})
    plant(name, 6, rows, "shape_constraint_failed")
    rows[8]["bar_mark"] = rows[7]["bar_mark"]
    plant(name, 8, rows, "duplicate_bar_mark")
    rows[9]["member"] = ""
    plant(name, 9, rows, "missing_value")
    rows[10]["bars_per_member"] = "2.5"
    plant(name, 10, rows, "invalid_quantity")
    rows[12]["cut_length_mm"] = "TBC"
    plant(name, 12, rows, "invalid_number")
    rows[13] = make_row(profile, "14", "Beam B4", 16, 2, 5, "11", {"A": 1800, "B": 400})
    rows[13]["b_mm"] = "-400"
    plant(name, 13, rows, "invalid_dimension")
    _write_csv(os.path.join(sched_dir, name), rows)
    _write_meta(os.path.join(sched_dir, "S-310_beams_rev_C.meta.json"),
                _header("S-310", "C"), _declared(profile, rows))

    # 4. Excel workbook with title-block and weight-summary errors: should FAIL.
    name = "S-402_slab_rev_A.xlsx"
    rows = [
        make_row(profile, "01", "Slab S1 bottom", 12, 1, 86, "00", {"A": 5950}),
        make_row(profile, "02", "Slab S1 bottom", 12, 1, 64, "00", {"A": 7450}),
        make_row(profile, "03", "Slab S1 top", 16, 1, 48, "11", {"A": 2400, "B": 350}),
        make_row(profile, "04", "Slab S1 top", 16, 1, 52, "21", {"A": 350, "B": 1800, "C": 350}),
        make_row(profile, "05", "Slab S2 bottom", 10, 2, 40, "00", {"A": 4200}),
        make_row(profile, "06", "Slab S2 top", 10, 2, 22, "41",
                 {"A": 300, "B": 250, "C": 600, "D": 250, "E": 300}),
        make_row(profile, "07", "Slab S2 top", 12, 2, 30, "11", {"A": 1500, "B": 300}),
    ]
    rows[6]["cut_length_mm"] = str(int(rows[6]["cut_length_mm"]) - 200)
    plant(name, 6, rows, "cut_length_mismatch")
    header = _header("S-402", "")
    header["checked_by"] = ""
    plant(name, None, rows, "header_missing")          # revision
    plant(name, None, rows, "header_missing")          # checked_by
    summary = _declared(profile, rows)
    for entry in summary:
        if entry["diameter_mm"] == 12:
            entry["total_weight_kg"] = round(entry["total_weight_kg"] * 0.92, 1)
    plant(name, None, rows, "summary_weight_mismatch")
    summary = [s for s in summary if s["diameter_mm"] != 16]
    plant(name, None, rows, "summary_diameter_missing")
    summary.append({"diameter_mm": 25, "total_weight_kg": 310.0})
    plant(name, None, rows, "summary_diameter_unexpected")
    _write_xlsx(os.path.join(sched_dir, name), rows, header, summary)

    # 5. Correct rows but no title block and no weight summary: should FAIL.
    name = "S-518_walls_rev_A.csv"
    rows = clean_rows(profile, rng, "walls", 10)
    _write_csv(os.path.join(sched_dir, name), rows)
    for _ in profile.required_header_fields:
        plant(name, None, rows, "header_missing")
    plant(name, None, rows, "no_weight_summary")

    with open(os.path.join(data_dir, "planted_defects.csv"), "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["schedule", "line", "bar_mark", "rule"],
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(planted)

    # Files that should be rejected or failed outright.
    with open(os.path.join(bad_dir, "missing_columns.csv"), "w", encoding="utf-8") as handle:
        handle.write("bar_mark,member,diameter_mm,total_bars,cut_length_mm\n01,Beam B1,16,12,4000\n")
    with open(os.path.join(bad_dir, "headers_only.csv"), "w", encoding="utf-8") as handle:
        handle.write(",".join(ALL_COLUMNS) + "\n")
    bad_profile = {
        "name": "Deliberately broken profile", "length_rounding_mm": 0, "cut_length_tolerance_mm": 25,
        "max_bar_length_mm": 12000, "steel_density_kg_m3": 7850, "summary_weight_tolerance_pct": 1,
        "diameters": {"12": {"min_former_radius_mm": 24, "min_end_projection_mm": 125}},
        "shapes": {
            "11": {"dimensions": ["A"], "formula": "A + B - 0.5*r - d"},
            "21": {"dimensions": ["A", "B", "C"], "formula": "__import__('os').getcwd()"},
        },
    }
    with open(os.path.join(bad_dir, "profile_invalid.json"), "w", encoding="utf-8") as handle:
        json.dump(bad_profile, handle, indent=2)
        handle.write("\n")
    return planted
