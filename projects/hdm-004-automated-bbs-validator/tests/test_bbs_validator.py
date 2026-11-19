"""Tests for the BBS validator. All data is synthetic."""
import copy
import csv
import json
import os
from collections import Counter

import pytest

import run
from bbs_validator import generate as gen
from bbs_validator.engine import exit_code, validate_file, validate_path
from bbs_validator.loaders import Schedule, ScheduleError, load_schedule
from bbs_validator.profile import (FormulaError, ProfileError, build_profile, evaluate,
                                   load_profile, parse_constraint, parse_formula)
from bbs_validator.report import write_outputs
from bbs_validator.rules import RULES, check_row, check_schedule, verdict

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
PROFILE_PATH = os.path.join(DATA, "profile_bs8666_style.json")


@pytest.fixture(scope="module")
def profile():
    return load_profile(PROFILE_PATH)


@pytest.fixture()
def raw_profile():
    with open(PROFILE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def row(profile, shape="11", d=16, dims=None, members=2, per=5, mark="01", **changes):
    """A correct row built from the profile, then changed as the test needs."""
    dims = dims or {"A": 1800, "B": 400}
    result = gen.make_row(profile, mark, "Beam B1", d, members, per, shape, dims)
    result["_line"] = 2
    result.update({k: str(v) for k, v in changes.items()})
    return result


def rules_of(findings):
    return sorted(f.rule for f in findings)


# ---------------------------------------------------------------- formulas

def test_formula_evaluates_plain_arithmetic():
    tree = parse_formula("2*(A + B) - 0.5*r - d")
    assert evaluate(tree, {"A": 100, "B": 50, "r": 32, "d": 16}) == pytest.approx(268)


@pytest.mark.parametrize("text", [
    "__import__('os').system('echo hi')", "A ** 2", "open('x')", "X + 1", "A if B else C",
    "[A]", "A +", "'text'", "True",
])
def test_formula_rejects_anything_but_arithmetic(text):
    with pytest.raises(FormulaError):
        parse_formula(text)


def test_constraint_true_and_false():
    con = parse_constraint("B >= 2*(r + d)")
    assert con.holds({"B": 180, "r": 70, "d": 20})
    assert not con.holds({"B": 179, "r": 70, "d": 20})
    with pytest.raises(FormulaError):
        parse_constraint("B > 10")


# ----------------------------------------------------------------- profile

def test_sample_profile_loads(profile):
    assert set(profile.shapes) == {"00", "11", "13", "21", "31", "33", "41", "44", "51", "63"}
    assert profile.diameters[20] == {"r": 70.0, "p": 190.0}


def test_unit_weight_matches_hand_calculation(profile):
    # 16 mm bar: pi * 0.016^2 / 4 * 7850 = 1.578 kg/m
    assert profile.unit_weight(16) == pytest.approx(1.578, abs=0.001)


def test_round_up_to_step(profile):
    assert profile.round_up(2152) == 2175
    assert profile.round_up(2175) == 2175
    assert profile.round_up(2175.2) == 2200


@pytest.mark.parametrize("change, expected", [
    (lambda p: p.update(length_rounding_mm=0), "length_rounding_mm"),
    (lambda p: p.update(diameters={}), "diameters"),
    (lambda p: p.update(shapes={}), "shapes"),
    (lambda p: p.update(bar_mark_pattern="["), "bar_mark_pattern"),
    (lambda p: p["shapes"]["11"].update(formula="A + B + C"), "not in 'dimensions'"),
    (lambda p: p["shapes"]["11"].update(dimensions=["A", "Z"]), "unique names"),
    (lambda p: p["shapes"]["11"].update(end_legs=["E"]), "end leg"),
    (lambda p: p["diameters"]["12"].update(min_former_radius_mm=-1), "diameter '12'"),
])
def test_profile_validation_reports_problem(raw_profile, change, expected):
    broken = copy.deepcopy(raw_profile)
    change(broken)
    with pytest.raises(ProfileError, match=expected):
        build_profile(broken)


def test_invalid_profile_lists_all_problems_together():
    with pytest.raises(ProfileError) as info:
        load_profile(os.path.join(DATA, "invalid", "profile_invalid.json"))
    text = str(info.value)
    assert "length_rounding_mm" in text and "shape '11'" in text and "shape '21'" in text


def test_profile_file_errors(tmp_path):
    with pytest.raises(ProfileError, match="cannot open"):
        load_profile(str(tmp_path / "nope.json"))
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProfileError, match="not valid JSON"):
        load_profile(str(bad))


# --------------------------------------------------------------- row rules

def test_correct_row_has_no_findings(profile):
    assert check_row(row(profile), profile) == []


def test_cut_length_hand_calculation(profile):
    # Shape 11, 16 mm bar, A 1800, B 400: 1800 + 400 - 0.5*32 - 16 = 2168 -> 2175
    assert row(profile)["cut_length_mm"] == "2175"
    # Shape 51, 10 mm link, A 300, B 550, C 120: 2*970 - 2.5*20 - 5*10 = 1840 -> 1850
    assert gen.cut_length(profile, "51", 10, {"A": 300, "B": 550, "C": 120}) == 1850


@pytest.mark.parametrize("shape, d, dims, expected", [
    ("00", 16, {"A": 5000}, 5000),
    ("11", 16, {"A": 1800, "B": 400}, 2168),                      # 2200 - 16 - 16
    ("13", 20, {"A": 900, "B": 200, "C": 900}, 1882),             # 900 + 114 + 900 - 32
    ("21", 20, {"A": 400, "B": 2400, "C": 400}, 3090),            # 3200 - 70 - 40
    ("31", 16, {"A": 400, "B": 600, "C": 700, "D": 400}, 2004),   # 2100 - 48 - 48
    ("33", 12, {"A": 800, "B": 200, "C": 500}, 2892),             # 1600 + 340 + 1000 - 48
    ("41", 10, {"A": 300, "B": 250, "C": 600, "D": 250, "E": 300}, 1620),   # 1700 - 40 - 40
    ("44", 10, {"A": 300, "B": 250, "C": 600, "D": 250, "E": 300}, 1620),
    ("51", 10, {"A": 300, "B": 550, "C": 120}, 1840),             # 1940 - 50 - 50
    ("63", 8, {"A": 300, "B": 250, "C": 130}, 1514),              # 1610 - 48 - 48
])
def test_each_shape_formula_against_hand_calculation(profile, shape, d, dims, expected):
    values = dict(dims, d=d, r=profile.diameters[d]["r"])
    assert evaluate(profile.shapes[shape].formula, values) == pytest.approx(expected)


def test_cut_length_tolerance_boundary(profile):
    assert check_row(row(profile, cut_length_mm=2200), profile) == []          # 25 mm off: allowed
    found = check_row(row(profile, cut_length_mm=2225), profile)               # 50 mm off: error
    assert rules_of(found) == ["cut_length_mismatch"]
    assert found[0].suggested == "2175" and found[0].severity == "error"


def test_total_bars_mismatch_suggests_value(profile):
    found = check_row(row(profile, total_bars=12), profile)
    assert rules_of(found) == ["total_bars_mismatch"] and found[0].suggested == "10"


@pytest.mark.parametrize("changes, rule", [
    ({"member": ""}, "missing_value"),
    ({"total_bars": ""}, "missing_value"),
    ({"cut_length_mm": "TBC"}, "invalid_number"),
    ({"cut_length_mm": "0"}, "invalid_number"),
    ({"no_of_members": "0"}, "invalid_quantity"),
    ({"bars_per_member": "2.5"}, "invalid_quantity"),
    ({"diameter_mm": "14"}, "non_standard_diameter"),
    ({"b_mm": ""}, "missing_dimension"),
    ({"b_mm": "abc"}, "invalid_dimension"),
    ({"b_mm": "-400"}, "invalid_dimension"),
    ({"shape_code": "99"}, "unknown_shape_code"),
    ({"c_mm": "250"}, "unused_dimension"),
    ({"bar_mark": "B-01/A"}, "bar_mark_format"),
])
def test_single_defect_gives_single_rule(profile, changes, rule):
    assert rules_of(check_row(row(profile, **changes), profile)) == [rule]


def test_leg_too_short_boundary(profile):
    # 25 mm bar: minimum end projection is 240 mm
    assert check_row(row(profile, d=25, dims={"A": 2600, "B": 240}), profile) == []
    assert rules_of(check_row(row(profile, d=25, dims={"A": 2600, "B": 235}), profile)) == ["leg_too_short"]


def test_shape_constraint(profile):
    bad = row(profile, shape="13", d=20, dims={"A": 900, "B": 100, "C": 900})
    assert rules_of(check_row(bad, profile)) == ["shape_constraint_failed"]


def test_not_rounded_and_too_long_are_warnings(profile):
    found = check_row(row(profile, shape="00", dims={"A": 13510}, cut_length_mm=13510), profile)
    assert rules_of(found) == ["cut_length_not_rounded", "exceeds_max_length"]
    assert {f.severity for f in found} == {"warning"}


def test_shape_code_without_leading_zero_and_zero_dimension(profile):
    straight = row(profile, shape="00", dims={"A": 3000}, shape_code="0", b_mm="0")
    assert check_row(straight, profile) == []


def test_number_with_thousands_separator(profile):
    assert check_row(row(profile, shape="00", dims={"A": 3000}, cut_length_mm="3,000"), profile) == []


# ---------------------------------------------------------- schedule rules

def full_schedule(profile, rows, summary="auto", header="auto"):
    for i, r in enumerate(rows):
        r["_line"] = i + 2
    if header == "auto":
        header = {f: "x" for f in profile.required_header_fields}
    if summary == "auto":
        summary = gen._declared(profile, rows)
    return Schedule("test.csv", rows, header, summary)


def test_clean_schedule_passes(profile):
    sched = full_schedule(profile, [row(profile, mark="01"), row(profile, mark="02", d=12, dims={"A": 900, "B": 300})])
    findings = check_schedule(sched, profile)
    assert findings == [] and verdict(findings) == "PASS"


def test_duplicate_bar_mark_reported_once_on_second_row(profile):
    sched = full_schedule(profile, [row(profile, mark="01"), row(profile, mark="02"), row(profile, mark="01")])
    found = check_schedule(sched, profile)
    assert rules_of(found) == ["duplicate_bar_mark"] and found[0].line == 4


def test_header_missing_field_and_no_header(profile):
    header = {f: "x" for f in profile.required_header_fields}
    header["revision"] = " "
    found = check_schedule(full_schedule(profile, [row(profile)], header=header), profile)
    assert [f.message for f in found] == ["Title-block field 'revision' is missing"]
    found = check_schedule(full_schedule(profile, [row(profile)], header=None), profile)
    assert rules_of(found) == ["header_missing"] * len(profile.required_header_fields)


def test_weight_summary_tolerance(profile):
    rows = [row(profile)]                    # 10 bars x 2.175 m x 1.578 kg/m = 34.33 kg
    ok = [{"diameter_mm": 16, "total_weight_kg": 34.5}]        # 0.5 % apart
    assert check_schedule(full_schedule(profile, rows, summary=ok), profile) == []
    bad = [{"diameter_mm": 16, "total_weight_kg": 36.0}]       # 4.9 % apart
    found = check_schedule(full_schedule(profile, rows, summary=bad), profile)
    assert rules_of(found) == ["summary_weight_mismatch"] and found[0].suggested == "34.3"


def test_summary_missing_unexpected_and_absent(profile):
    rows = [row(profile)]
    found = check_schedule(full_schedule(profile, rows, summary=[{"diameter_mm": 25, "total_weight_kg": 5}]), profile)
    assert rules_of(found) == ["summary_diameter_missing", "summary_diameter_unexpected"]
    found = check_schedule(full_schedule(profile, rows, summary=None), profile)
    assert rules_of(found) == ["no_weight_summary"] and verdict(found) == "REVIEW"


def test_unusable_row_skips_reconciliation_with_note(profile):
    rows = [row(profile, mark="01"), row(profile, mark="02", cut_length_mm="TBC")]
    sched = full_schedule(profile, rows, summary=[{"diameter_mm": 16, "total_weight_kg": 1}])
    assert rules_of(check_schedule(sched, profile)) == ["invalid_number"]
    assert len(sched.notes) == 1 and "16 mm" in sched.notes[0]


def test_empty_schedule_fails(profile):
    found = check_schedule(full_schedule(profile, [], summary=[]), profile)
    assert rules_of(found) == ["empty_schedule"] and verdict(found) == "FAIL"


# ----------------------------------------------------------------- loaders

def test_csv_and_xlsx_give_same_rows(profile, tmp_path):
    rows = [row(profile, mark="01"), row(profile, mark="02", shape="00", dims={"A": 4000})]
    clean = [{k: v for k, v in r.items() if k != "_line"} for r in rows]
    header = {f: "x" for f in profile.required_header_fields}
    summary = gen._declared(profile, clean)
    gen._write_csv(str(tmp_path / "a.csv"), clean)
    gen._write_meta(str(tmp_path / "a.meta.json"), header, summary)
    gen._write_xlsx(str(tmp_path / "b.xlsx"), clean, header, summary)
    from_csv, from_xlsx = load_schedule(str(tmp_path / "a.csv")), load_schedule(str(tmp_path / "b.xlsx"))
    assert from_csv.rows == from_xlsx.rows
    assert from_csv.header == from_xlsx.header
    assert check_schedule(from_csv, profile) == [] and check_schedule(from_xlsx, profile) == []


def test_loader_accepts_reordered_headers_and_blank_lines(tmp_path):
    path = tmp_path / "s.csv"
    path.write_text("Member,Bar Mark,Diameter mm,No of members,Bars per member,Total bars,"
                    "Shape code,A mm,Cut length mm\n\nBeam B1,01,16,2,5,10,00,4000,4000\n", encoding="utf-8")
    sched = load_schedule(str(path))
    assert len(sched.rows) == 1 and sched.rows[0]["bar_mark"] == "01" and sched.rows[0]["_line"] == 3
    assert sched.header is None and sched.summary is None


def test_unreadable_inputs(tmp_path):
    with pytest.raises(ScheduleError, match="missing column"):
        load_schedule(os.path.join(DATA, "invalid", "missing_columns.csv"))
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ScheduleError, match="empty"):
        load_schedule(str(empty))
    fake = tmp_path / "fake.xlsx"
    fake.write_text("this is not a workbook", encoding="utf-8")
    with pytest.raises(ScheduleError, match="cannot open workbook"):
        load_schedule(str(fake))
    with pytest.raises(ScheduleError, match="unsupported"):
        load_schedule(str(tmp_path / "x.pdf"))
    (tmp_path / "m.csv").write_text((open(os.path.join(DATA, "invalid", "headers_only.csv")).read()), encoding="utf-8")
    (tmp_path / "m.meta.json").write_text("[1, 2", encoding="utf-8")
    with pytest.raises(ScheduleError, match="meta.json"):
        load_schedule(str(tmp_path / "m.csv"))


# ------------------------------------------------- end to end on sample data

@pytest.fixture(scope="module")
def sample_results(profile):
    return validate_path(os.path.join(DATA, "schedules"), profile)


def test_sample_verdicts(sample_results):
    assert {r.name: r.verdict for r in sample_results} == {
        "S-101_footings_rev_B.csv": "PASS",
        "S-205_columns_rev_A.csv": "REVIEW",
        "S-310_beams_rev_C.csv": "FAIL",
        "S-402_slab_rev_A.xlsx": "FAIL",
        "S-518_walls_rev_A.csv": "FAIL",
    }


def test_findings_equal_planted_defects_exactly(sample_results):
    """Every planted defect is found with the right rule, and nothing else is reported."""
    with open(os.path.join(DATA, "planted_defects.csv"), newline="", encoding="utf-8") as handle:
        planted = Counter((r["schedule"], r["line"], r["bar_mark"], r["rule"]) for r in csv.DictReader(handle))
    found = Counter((f.schedule, str(f.line or ""), f.bar_mark, f.rule)
                    for r in sample_results for f in r.findings)
    assert found == planted
    assert sum(planted.values()) == 29


def test_generator_is_repeatable(profile, tmp_path):
    first = gen.generate(profile, str(tmp_path / "one"))
    second = gen.generate(profile, str(tmp_path / "two"))
    assert first == second
    for name in ("S-101_footings_rev_B.csv", "S-310_beams_rev_C.csv"):
        assert (tmp_path / "one" / "schedules" / name).read_text() == \
            (tmp_path / "two" / "schedules" / name).read_text() == \
            open(os.path.join(DATA, "schedules", name)).read()


def test_every_rule_is_exercised_somewhere(sample_results, profile):
    seen = {f.rule for r in sample_results for f in r.findings}
    seen |= {f.rule for f in validate_file(os.path.join(DATA, "invalid", "headers_only.csv"), profile).findings}
    assert seen == set(RULES)


def test_batch_continues_past_unreadable_file(profile):
    results = validate_path(os.path.join(DATA, "invalid"), profile)
    by_name = {r.name: r for r in results}
    assert by_name["missing_columns.csv"].verdict == "UNREADABLE"
    assert "missing column" in by_name["missing_columns.csv"].problem
    assert by_name["headers_only.csv"].verdict == "FAIL"
    assert exit_code(results) == 1


def test_exit_code_strict(sample_results):
    passed = [r for r in sample_results if r.verdict == "PASS"]
    review = [r for r in sample_results if r.verdict == "REVIEW"]
    assert exit_code(passed) == 0
    assert exit_code(review) == 0 and exit_code(review, strict=True) == 1


def test_outputs_written_and_consistent(sample_results, profile, tmp_path):
    summary = write_outputs(sample_results, profile.name, str(tmp_path))
    with open(tmp_path / "findings.csv", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == summary["errors"] + summary["warnings"] == 29
    assert summary["verdicts"] == {"PASS": 1, "REVIEW": 1, "FAIL": 3, "UNREADABLE": 0}
    assert json.loads((tmp_path / "summary.json").read_text())["bar_rows_checked"] == 59
    page = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "S-402_slab_rev_A.xlsx" in page and "Not an engineering approval" in page


def test_report_escapes_html(profile, tmp_path):
    bad = row(profile, bar_mark="<b>x")
    sched = full_schedule(profile, [bad])
    path = tmp_path / "in.csv"
    gen._write_csv(str(path), [{k: v for k, v in bad.items() if k != "_line"}])
    result = validate_file(str(path), profile)
    write_outputs([result], profile.name, str(tmp_path / "out"))
    assert "<b>x" not in (tmp_path / "out" / "report.html").read_text(encoding="utf-8")
    assert sched.rows[0]["bar_mark"] == "<b>x"


# --------------------------------------------------------------------- CLI

def test_cli_validate_folder_and_single_file(tmp_path, capsys):
    assert run.main(["validate", os.path.join(DATA, "schedules"), "--out-dir", str(tmp_path)]) == 1
    assert os.path.exists(tmp_path / "report.html")
    clean = os.path.join(DATA, "schedules", "S-101_footings_rev_B.csv")
    assert run.main(["validate", clean, "--out-dir", str(tmp_path)]) == 0
    review = os.path.join(DATA, "schedules", "S-205_columns_rev_A.csv")
    assert run.main(["validate", review, "--out-dir", str(tmp_path)]) == 0
    assert run.main(["validate", review, "--out-dir", str(tmp_path), "--strict"]) == 1
    assert "REVIEW" in capsys.readouterr().out


def test_cli_usage_errors(tmp_path, capsys):
    assert run.main(["validate", str(tmp_path / "missing"), "--out-dir", str(tmp_path)]) == 2
    assert run.main(["validate", str(tmp_path), "--out-dir", str(tmp_path)]) == 2
    bad = os.path.join(DATA, "invalid", "profile_invalid.json")
    assert run.main(["--profile", bad, "validate", DATA, "--out-dir", str(tmp_path)]) == 2
    assert "invalid profile" in capsys.readouterr().err


def test_cli_shapes_and_rules(capsys):
    assert run.main(["shapes"]) == 0 and run.main(["rules"]) == 0
    out = capsys.readouterr().out
    assert "A + B - 0.5*r - d" in out and "cut_length_mismatch" in out
