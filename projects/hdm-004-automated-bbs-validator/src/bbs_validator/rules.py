"""The validation rules.

Two severities are used:
  error    a definite defect in the schedule; it must be corrected
  warning  something a person has to look at; it may be intentional

RULES is the single catalogue of rule ids, so reports and tests share one list.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from .loaders import Schedule
from .profile import DIM_NAMES, Profile, evaluate

ERROR, WARNING = "error", "warning"

RULES = {
    "missing_value":             (ERROR,   "A required cell is empty"),
    "invalid_number":            (ERROR,   "A numeric cell does not hold a number"),
    "invalid_quantity":          (ERROR,   "A quantity is not a whole number above zero"),
    "non_standard_diameter":     (ERROR,   "Bar size is not in the profile"),
    "total_bars_mismatch":       (ERROR,   "Total bars is not members x bars per member"),
    "missing_dimension":         (ERROR,   "The shape needs a dimension that is empty"),
    "invalid_dimension":         (ERROR,   "A dimension is not a number above zero"),
    "shape_constraint_failed":   (ERROR,   "Dimensions cannot form the shape"),
    "leg_too_short":             (ERROR,   "An end leg is shorter than the minimum end projection"),
    "cut_length_mismatch":       (ERROR,   "Cut length differs from the shape-code calculation"),
    "duplicate_bar_mark":        (ERROR,   "A bar mark is used on more than one row"),
    "empty_schedule":            (ERROR,   "The schedule has no bar rows"),
    "header_missing":            (ERROR,   "A required title-block field is empty or absent"),
    "summary_weight_mismatch":   (ERROR,   "Declared weight differs from the weight of the rows"),
    "summary_diameter_missing":  (ERROR,   "A bar size in the rows is absent from the weight summary"),
    "summary_diameter_unexpected": (ERROR, "The weight summary lists a bar size that has no rows"),
    "unknown_shape_code":        (WARNING, "Shape code is not in the profile, so it cannot be checked"),
    "unused_dimension":          (WARNING, "A dimension is filled in that the shape does not use"),
    "cut_length_not_rounded":    (WARNING, "Cut length is not a multiple of the rounding step"),
    "exceeds_max_length":        (WARNING, "Cut length is longer than the maximum bar length"),
    "bar_mark_format":           (WARNING, "Bar mark does not match the expected format"),
    "no_weight_summary":         (WARNING, "No weight summary was supplied, so totals were not reconciled"),
}


@dataclass(frozen=True)
class Finding:
    schedule: str
    line: int            # line in the source file, 0 for schedule-level findings
    bar_mark: str
    rule: str
    severity: str
    message: str
    suggested: str = ""


def _finding(schedule, line, mark, rule, message, suggested=""):
    return Finding(schedule, line, mark, rule, RULES[rule][0], message, suggested)


def _number(text):
    try:
        value = float(str(text).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return value if value == value and abs(value) != float("inf") else None


def _fmt(value: float) -> str:
    return f"{value:g}" if abs(value - round(value)) > 1e-9 else str(int(round(value)))


def check_row(row: dict, profile: Profile, schedule: str = "") -> list:
    """All checks that need only one row."""
    line = row.get("_line", 0)
    mark = str(row.get("bar_mark", "")).strip()
    out: list = []

    def add(rule, message, suggested=""):
        out.append(_finding(schedule, line, mark, rule, message, suggested))

    for col in ("bar_mark", "member", "shape_code"):
        if not str(row.get(col, "")).strip():
            add("missing_value", f"{col} is empty")
    if mark and not re.fullmatch(profile.bar_mark_pattern, mark):
        add("bar_mark_format", f"Bar mark '{mark}' does not match pattern {profile.bar_mark_pattern}")

    nums: dict = {}
    for col in ("diameter_mm", "no_of_members", "bars_per_member", "total_bars", "cut_length_mm"):
        text = str(row.get(col, "")).strip()
        if not text:
            add("missing_value", f"{col} is empty")
            continue
        value = _number(text)
        if value is None:
            add("invalid_number", f"{col} '{text}' is not a number")
        elif col == "cut_length_mm" and value <= 0:
            add("invalid_number", f"cut_length_mm must be above zero, found {text}")
        elif col in ("no_of_members", "bars_per_member", "total_bars") \
                and (value <= 0 or value != int(value)):
            add("invalid_quantity", f"{col} must be a whole number above zero, found {text}")
        else:
            nums[col] = value

    if {"no_of_members", "bars_per_member", "total_bars"} <= nums.keys():
        want = nums["no_of_members"] * nums["bars_per_member"]
        if nums["total_bars"] != want:
            add("total_bars_mismatch",
                f"Total bars {_fmt(nums['total_bars'])}, expected {_fmt(nums['no_of_members'])} x "
                f"{_fmt(nums['bars_per_member'])} = {_fmt(want)}", _fmt(want))

    cut = nums.get("cut_length_mm")
    if cut is not None:
        if abs(cut / profile.length_rounding_mm - round(cut / profile.length_rounding_mm)) > 1e-6:
            add("cut_length_not_rounded",
                f"Cut length {_fmt(cut)} mm is not a multiple of {_fmt(profile.length_rounding_mm)} mm",
                _fmt(profile.round_up(cut)))
        if cut > profile.max_bar_length_mm:
            add("exceeds_max_length",
                f"Cut length {_fmt(cut)} mm is longer than {_fmt(profile.max_bar_length_mm)} mm "
                f"(lap, coupler or special delivery to be confirmed)")

    dia = nums.get("diameter_mm")
    limits = profile.diameters.get(int(dia)) if dia is not None and dia == int(dia) else None
    if dia is not None and limits is None:
        sizes = ", ".join(str(s) for s in sorted(profile.diameters))
        add("non_standard_diameter", f"Diameter {_fmt(dia)} mm is not in the profile ({sizes})")

    code_text = str(row.get("shape_code", "")).strip()
    if not code_text:
        return out
    code = code_text.zfill(2)
    shape = profile.shapes.get(code)
    if shape is None:
        add("unknown_shape_code", f"Shape code {code} is not in the profile; cut length not checked")
        return out

    dims: dict = {}
    dims_ok = True
    for name in DIM_NAMES:
        text = str(row.get(f"{name.lower()}_mm", "")).strip()
        value = _number(text) if text else None
        if name in shape.dimensions:
            if not text:
                add("missing_dimension", f"Shape {code} needs dimension {name}")
                dims_ok = False
            elif value is None or value <= 0:
                add("invalid_dimension", f"Dimension {name} must be a number above zero, found '{text}'")
                dims_ok = False
            else:
                dims[name] = value
        elif text and value != 0:
            add("unused_dimension", f"Dimension {name} = {text} is not used by shape {code}")

    if not dims_ok or limits is None:
        return out                       # geometry cannot be checked without valid inputs

    values = dict(dims, d=dia, r=limits["r"])
    for constraint in shape.constraints:
        if not constraint.holds(values):
            add("shape_constraint_failed",
                f"Shape {code} requires {constraint.text} (r = {_fmt(limits['r'])}, d = {_fmt(dia)})")
    for leg in shape.end_legs:
        if dims[leg] < limits["p"]:
            add("leg_too_short",
                f"Leg {leg} = {_fmt(dims[leg])} mm is below the minimum end projection "
                f"{_fmt(limits['p'])} mm for a {_fmt(dia)} mm bar")

    if cut is not None:
        raw = evaluate(shape.formula, values)
        want = profile.round_up(raw)
        if abs(cut - want) > profile.cut_length_tolerance_mm + 1e-9:
            add("cut_length_mismatch",
                f"Cut length {_fmt(cut)} mm, shape {code} gives {shape.formula_text} = {raw:.0f}, "
                f"rounded up to {_fmt(want)} mm", _fmt(want))
    return out


def computed_weights(schedule: Schedule, profile: Profile):
    """Weight in kg per bar size from the rows, plus sizes that could not be totalled."""
    totals: dict = defaultdict(float)
    unusable: set = set()
    for row in schedule.rows:
        dia = _number(row.get("diameter_mm", ""))
        if dia is None or dia != int(dia):
            continue
        dia = int(dia)
        bars, cut = _number(row.get("total_bars", "")), _number(row.get("cut_length_mm", ""))
        if dia not in profile.diameters or bars is None or cut is None or bars <= 0 or cut <= 0:
            unusable.add(dia)
            continue
        totals[dia] += bars * cut / 1000.0 * profile.unit_weight(dia)
    return dict(totals), unusable


def check_schedule(schedule: Schedule, profile: Profile) -> list:
    """Row checks plus the checks that need the whole schedule."""
    name = schedule.name
    out: list = []
    if not schedule.rows:
        out.append(_finding(name, 0, "", "empty_schedule", "The schedule has no bar rows"))
    for row in schedule.rows:
        out.extend(check_row(row, profile, name))

    first_seen: dict = {}
    for row in schedule.rows:
        mark = str(row.get("bar_mark", "")).strip()
        if not mark:
            continue
        if mark in first_seen:
            out.append(_finding(name, row["_line"], mark, "duplicate_bar_mark",
                                f"Bar mark {mark} was already used on line {first_seen[mark]}"))
        else:
            first_seen[mark] = row["_line"]

    header = schedule.header
    for fld in profile.required_header_fields:
        if header is None or not str(header.get(fld, "")).strip():
            out.append(_finding(name, 0, "", "header_missing", f"Title-block field '{fld}' is missing"))

    if schedule.summary is None:
        if schedule.rows:
            out.append(_finding(name, 0, "", "no_weight_summary",
                                "No weight summary supplied; row totals were not reconciled"))
        return out

    totals, unusable = computed_weights(schedule, profile)
    declared: dict = {}
    for entry in schedule.summary:
        dia, weight = _number(entry.get("diameter_mm")), _number(entry.get("total_weight_kg"))
        if dia is not None and weight is not None:
            declared[int(dia)] = weight
    for dia in sorted(set(totals) | set(declared) | unusable):
        if dia in unusable:
            note = (f"Weight for {dia} mm bars was not reconciled because at least "
                    f"one row of that size has unusable values.")
            if note not in schedule.notes:
                schedule.notes.append(note)
            continue
        if dia not in declared:
            out.append(_finding(name, 0, "", "summary_diameter_missing",
                                f"{dia} mm bars weigh {totals[dia]:.1f} kg in the rows but are not "
                                f"in the weight summary", f"{totals[dia]:.1f}"))
        elif dia not in totals:
            out.append(_finding(name, 0, "", "summary_diameter_unexpected",
                                f"Weight summary declares {declared[dia]:.1f} kg of {dia} mm bars "
                                f"but no row uses that size"))
        else:
            diff_pct = abs(declared[dia] - totals[dia]) / totals[dia] * 100.0
            if diff_pct > profile.summary_weight_tolerance_pct:
                out.append(_finding(name, 0, "", "summary_weight_mismatch",
                                    f"{dia} mm bars: summary declares {declared[dia]:.1f} kg, rows give "
                                    f"{totals[dia]:.1f} kg ({diff_pct:.1f}% apart)", f"{totals[dia]:.1f}"))
    return out


def verdict(findings: list) -> str:
    """FAIL if any error, REVIEW if only warnings, PASS if nothing was found."""
    severities = {f.severity for f in findings}
    if ERROR in severities:
        return "FAIL"
    return "REVIEW" if WARNING in severities else "PASS"
