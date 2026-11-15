"""Synthetic BBS generator with known, injected defects (ground truth).

Nothing here comes from a real project. Each row is random but internally
consistent, then selected rows are deliberately broken so the checker and the
review workflow can be measured against a known answer.
"""
from __future__ import annotations

import random

from .checks import COLUMNS, expected_cut_length, unit_weight

# case name -> (number of rows, counts as a real defect?)
CASES = {
    "wrong_unit_weight": (3, True),
    "wrong_total_bars": (3, True),
    "wrong_total_weight": (3, True),
    "cut_length_gross": (3, True),
    "cut_length_short": (3, True),       # 40-90 mm short: ambiguous to a machine
    "benign_rounding": (4, False),       # 30-60 mm long: detailer's allowance
    "over_stock_length": (2, True),
    "unsupported_shape": (2, False),     # valid bar, checker just cannot verify it
    "non_standard_diameter": (2, True),
    "missing_value": (2, True),
    "duplicate_mark": (1, True),         # copies the previous row's bar mark
}
MEMBERS = ["Footing F1", "Footing F2", "Column C1", "Column C2", "Beam B1", "Beam B2",
           "Slab S1", "Wall W1", "Pile cap PC1", "Stair ST1"]


def _round25(x: float) -> int:
    return int(round(x / 25.0) * 25)


def _clean_row(rng: random.Random, row_id: int) -> dict:
    d = rng.choice([8, 10, 12, 16, 20, 25, 32])
    shape = rng.choice(["00", "00", "11", "21", "51"])
    a = b = c = 0
    if shape == "00":
        a = rng.randrange(1000, 11500, 25)
    elif shape == "11":
        a, b = rng.randrange(800, 6000, 25), rng.randrange(200, 900, 25)
    elif shape == "21":
        a, b, c = rng.randrange(300, 900, 25), rng.randrange(800, 5000, 25), rng.randrange(300, 900, 25)
    else:
        a, b, c = rng.randrange(200, 700, 25), rng.randrange(200, 900, 25), rng.choice([75, 100, 125])
    members, bars = rng.randint(1, 12), rng.randint(2, 24)
    length = _round25(expected_cut_length(shape, d, a, b, c))
    uw = unit_weight(d)
    return {
        "row_id": row_id, "bar_mark": f"{row_id:03d}", "member": rng.choice(MEMBERS),
        "shape_code": shape, "diameter_mm": d, "a_mm": a, "b_mm": b, "c_mm": c,
        "no_of_members": members, "bars_per_member": bars, "total_bars": members * bars,
        "cut_length_mm": length, "unit_weight_kg_m": round(uw, 3),
        "total_weight_kg": round(members * bars * length / 1000.0 * uw, 2),
    }


def _reweigh(row: dict) -> None:
    row["total_weight_kg"] = round(
        row["total_bars"] * row["cut_length_mm"] / 1000.0 * unit_weight(row["diameter_mm"]), 2)


def _inject(rng: random.Random, row: dict, case: str, previous: dict) -> None:
    if case == "wrong_unit_weight":
        row["unit_weight_kg_m"] = round(row["unit_weight_kg_m"] * rng.choice([0.85, 1.2]), 3)
    elif case == "wrong_total_bars":
        row["total_bars"] += rng.choice([-2, 3, 10])
        _reweigh(row)
    elif case == "wrong_total_weight":
        row["total_weight_kg"] = round(row["total_weight_kg"] * rng.choice([0.5, 1.1, 10]), 2)
    elif case == "cut_length_gross":
        row["cut_length_mm"] += rng.choice([-500, 300, 1000])
        _reweigh(row)
    elif case == "cut_length_short":
        row["cut_length_mm"] -= rng.choice([50, 75])
        _reweigh(row)
    elif case == "benign_rounding":
        row["cut_length_mm"] += 50
        _reweigh(row)
    elif case == "over_stock_length":
        row.update(shape_code="00", a_mm=13500, b_mm=0, c_mm=0, cut_length_mm=13500)
        _reweigh(row)
    elif case == "unsupported_shape":
        row.update(shape_code="99", cut_length_mm=_round25(row["a_mm"] + row["b_mm"] + 400))
        _reweigh(row)
    elif case == "non_standard_diameter":
        row["diameter_mm"] = rng.choice([14, 18, 22])
    elif case == "missing_value":
        row[rng.choice(["cut_length_mm", "total_bars", "diameter_mm"])] = ""
    elif case == "duplicate_mark":
        row["bar_mark"] = previous["bar_mark"]
    else:
        raise ValueError(case)


def generate(n_rows: int = 60, seed: int = 7) -> tuple[list[dict], list[dict]]:
    """Return (bbs_rows, truth_rows). truth has row_id, injected_case, is_defect."""
    needed = sum(n for n, _ in CASES.values())
    if n_rows < needed + 5:
        raise ValueError(f"n_rows must be at least {needed + 5}")
    rng = random.Random(seed)
    rows = [_clean_row(rng, i) for i in range(1, n_rows + 1)]
    truth = {i: ("none", False) for i in range(1, n_rows + 1)}
    # keep row 1 clean and never pick neighbours, so a duplicate mark has a clean partner
    targets = rng.sample(range(2, n_rows + 1, 2), needed)
    cases = [name for name, (n, _) in CASES.items() for _ in range(n)]
    for rid, case in zip(targets, cases):
        _inject(rng, rows[rid - 1], case, rows[rid - 2])
        truth[rid] = (case, CASES[case][1])
        if case == "duplicate_mark":
            truth[rid - 1] = (case, True)
    truth_rows = [{"row_id": rid, "injected_case": c, "is_defect": int(bad)}
                  for rid, (c, bad) in truth.items()]
    return rows, truth_rows


__all__ = ["generate", "CASES", "COLUMNS"]
