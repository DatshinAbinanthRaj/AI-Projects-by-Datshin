"""Automated checks for Bar Bending Schedule (BBS) rows.

Every check returns Findings. A finding is either *certain* (pure arithmetic or
a fixed rule, safe to send straight back to the detailer) or *uncertain*
(needs engineering judgement, so a human must look at it).

The bending formulas are simplified versions of common BS 8666-style shape
codes. They are for demonstration and are NOT a code-compliance check.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

COLUMNS = [
    "row_id", "bar_mark", "member", "shape_code", "diameter_mm", "a_mm", "b_mm",
    "c_mm", "no_of_members", "bars_per_member", "total_bars", "cut_length_mm",
    "unit_weight_kg_m", "total_weight_kg",
]
NUMERIC = COLUMNS[4:]
STANDARD_DIAMETERS = (8, 10, 12, 16, 20, 25, 32, 40)
STOCK_LENGTH_MM = 12000
WEIGHT_TOLERANCE = 0.02        # 2 % relative difference allowed
LENGTH_OK_MM = 25              # schedules round cut lengths to 25 mm
LENGTH_AMBIGUOUS_MM = 100      # between 25 and 100 mm a human decides


@dataclass(frozen=True)
class Finding:
    row_id: int
    rule: str
    certain: bool
    message: str
    suggested: str = ""


def unit_weight(diameter_mm: float) -> float:
    """Theoretical steel bar weight in kg/m (d squared / 162)."""
    return diameter_mm ** 2 / 162.0


def bend_radius(diameter_mm: float) -> float:
    """Minimum former radius: 2d up to 16 mm bars, 3.5d above."""
    return 2 * diameter_mm if diameter_mm <= 16 else 3.5 * diameter_mm


def expected_cut_length(shape_code: str, d: float, a: float, b: float, c: float):
    """Return the expected cut length in mm, or None for an unsupported shape."""
    r = bend_radius(d)
    code = shape_code.strip().zfill(2)
    if code == "00":                       # straight bar
        return a
    if code == "11":                       # one 90 degree bend
        return a + b - 0.5 * r - d
    if code == "21":                       # two 90 degree bends (U bar)
        return a + b + c - r - 2 * d
    if code == "51":                       # closed link
        return 2 * (a + b + c) - 2.5 * r - 5 * d
    return None


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


def check_row(row: dict) -> list[Finding]:
    rid = int(row["row_id"])
    missing = [c for c in NUMERIC if not _is_number(row.get(c, ""))]
    if not str(row.get("bar_mark", "")).strip():
        missing.insert(0, "bar_mark")
    if missing:
        return [Finding(rid, "missing_value", True,
                        "Missing or non-numeric: " + ", ".join(missing))]

    v = {c: float(row[c]) for c in NUMERIC}
    d = v["diameter_mm"]
    out: list[Finding] = []

    if d not in STANDARD_DIAMETERS:
        out.append(Finding(rid, "non_standard_diameter", True,
                           f"Diameter {d:g} mm is not a standard bar size"))
        return out  # weight and bend checks are meaningless for an invalid size

    uw = unit_weight(d)
    if abs(v["unit_weight_kg_m"] - uw) / uw > WEIGHT_TOLERANCE:
        out.append(Finding(rid, "unit_weight_mismatch", True,
                           f"Unit weight {v['unit_weight_kg_m']:g} kg/m, expected {uw:.3f}",
                           f"{uw:.3f}"))

    want_bars = v["no_of_members"] * v["bars_per_member"]
    if v["total_bars"] != want_bars:
        out.append(Finding(rid, "total_bars_mismatch", True,
                           f"Total bars {v['total_bars']:g}, expected "
                           f"{v['no_of_members']:g} x {v['bars_per_member']:g} = {want_bars:g}",
                           f"{want_bars:g}"))

    want_len = expected_cut_length(str(row["shape_code"]), d, v["a_mm"], v["b_mm"], v["c_mm"])
    if want_len is None:
        out.append(Finding(rid, "unsupported_shape_code", False,
                           f"Shape code {row['shape_code']} is not covered by the checker"))
    else:
        diff = abs(v["cut_length_mm"] - want_len)
        if diff > LENGTH_AMBIGUOUS_MM:
            out.append(Finding(rid, "cut_length_error", True,
                               f"Cut length {v['cut_length_mm']:g} mm, expected about {want_len:.0f}",
                               f"{want_len:.0f}"))
        elif diff > LENGTH_OK_MM:
            out.append(Finding(rid, "cut_length_deviation", False,
                               f"Cut length {v['cut_length_mm']:g} mm differs from the calculated "
                               f"{want_len:.0f} by {diff:.0f} mm (rounding, allowance or error?)"))

    if v["cut_length_mm"] > STOCK_LENGTH_MM:
        out.append(Finding(rid, "exceeds_stock_length", False,
                           f"Cut length {v['cut_length_mm']:g} mm is longer than a "
                           f"{STOCK_LENGTH_MM} mm stock bar (lap or coupler decision needed)"))

    want_wt = v["total_bars"] * v["cut_length_mm"] / 1000.0 * uw
    if want_wt > 0 and abs(v["total_weight_kg"] - want_wt) / want_wt > WEIGHT_TOLERANCE:
        out.append(Finding(rid, "total_weight_mismatch", True,
                           f"Total weight {v['total_weight_kg']:g} kg, expected {want_wt:.2f}",
                           f"{want_wt:.2f}"))
    return out


def check_schedule(rows: list[dict]) -> list[Finding]:
    """Run all row checks plus schedule-level checks (duplicate bar marks)."""
    findings: list[Finding] = []
    for row in rows:
        findings.extend(check_row(row))
    counts = Counter(str(r.get("bar_mark", "")).strip() for r in rows)
    for row in rows:
        mark = str(row.get("bar_mark", "")).strip()
        if mark and counts[mark] > 1:
            findings.append(Finding(int(row["row_id"]), "duplicate_bar_mark", True,
                                    f"Bar mark {mark} is used on {counts[mark]} rows"))
    return findings
