import pytest

from rebar_qa.checks import check_row, check_schedule, expected_cut_length, unit_weight
from rebar_qa.cli import main
from rebar_qa.generate import CASES, generate
from rebar_qa.workflow import (AUTO_ACCEPT, AUTO_FLAG, HUMAN_REVIEW, QA_SAMPLE, Store,
                               evaluate, triage)


def good_row(**changes):
    row = {"row_id": "1", "bar_mark": "001", "member": "Beam B1", "shape_code": "00",
           "diameter_mm": "16", "a_mm": "4000", "b_mm": "0", "c_mm": "0",
           "no_of_members": "2", "bars_per_member": "5", "total_bars": "10",
           "cut_length_mm": "4000", "unit_weight_kg_m": "1.580", "total_weight_kg": "63.21"}
    row.update({k: str(v) for k, v in changes.items()})
    return row


def rules(row):
    return [f.rule for f in check_row(row)]


def test_unit_weight_formula():
    assert unit_weight(16) == pytest.approx(1.580, abs=0.001)
    assert unit_weight(12) == pytest.approx(0.889, abs=0.001)


def test_expected_cut_lengths():
    assert expected_cut_length("00", 16, 4000, 0, 0) == 4000
    # one bend, 12 mm bar: r = 24, so A + B - 12 - 12
    assert expected_cut_length("11", 12, 1000, 300, 0) == 1276
    # 25 mm bar uses r = 3.5d = 87.5
    assert expected_cut_length("21", 25, 500, 2000, 500) == pytest.approx(3000 - 87.5 - 50)
    assert expected_cut_length("99", 12, 1, 1, 1) is None


def test_clean_row_has_no_findings():
    assert check_row(good_row()) == []


@pytest.mark.parametrize("changes, rule", [
    ({"unit_weight_kg_m": 1.9}, "unit_weight_mismatch"),
    ({"total_bars": 12, "total_weight_kg": 75.85}, "total_bars_mismatch"),
    ({"total_weight_kg": 90}, "total_weight_mismatch"),
    ({"cut_length_mm": 4500, "total_weight_kg": 71.11}, "cut_length_error"),
    ({"diameter_mm": 14}, "non_standard_diameter"),
    ({"cut_length_mm": ""}, "missing_value"),
    ({"bar_mark": " "}, "missing_value"),
])
def test_certain_errors(changes, rule):
    found = check_row(good_row(**changes))
    assert [f.rule for f in found] == [rule]
    assert found[0].certain


@pytest.mark.parametrize("changes, rule", [
    ({"cut_length_mm": 4050, "total_weight_kg": 64.0}, "cut_length_deviation"),
    ({"shape_code": "99"}, "unsupported_shape_code"),
    ({"a_mm": 13500, "cut_length_mm": 13500, "total_weight_kg": 213.33}, "exceeds_stock_length"),
])
def test_uncertain_findings_need_a_human(changes, rule):
    found = check_row(good_row(**changes))
    assert [f.rule for f in found] == [rule]
    assert not found[0].certain


def test_length_within_rounding_tolerance_is_accepted():
    assert rules(good_row(cut_length_mm=4025, total_weight_kg=63.6)) == []


def test_suggested_correction_is_given():
    f = check_row(good_row(total_bars=12, total_weight_kg=75.85))[0]
    assert f.suggested == "10"


def test_duplicate_bar_marks_flag_both_rows():
    rows = [good_row(), good_row(row_id=2)]
    found = check_schedule(rows)
    assert sorted(f.row_id for f in found if f.rule == "duplicate_bar_mark") == [1, 2]


def test_triage_routes():
    rows = [good_row(row_id=1, bar_mark="A"),
            good_row(row_id=2, bar_mark="B", total_weight_kg=90),
            good_row(row_id=3, bar_mark="C", shape_code="99"),
            good_row(row_id=4, bar_mark="D", shape_code="99", total_weight_kg=90)]
    routes = triage([1, 2, 3, 4], check_schedule(rows), sample_rate=0)
    assert routes == {1: AUTO_ACCEPT, 2: AUTO_FLAG, 3: HUMAN_REVIEW, 4: HUMAN_REVIEW}


def test_qa_sampling_is_seeded_and_only_touches_clean_rows():
    ids = list(range(1, 41))
    a = triage(ids, [], sample_rate=0.1, seed=3)
    b = triage(ids, [], sample_rate=0.1, seed=3)
    assert a == b
    assert sum(r == QA_SAMPLE for r in a.values()) == 4
    assert triage([1], [], sample_rate=0.1)[1] == QA_SAMPLE  # at least one sample
    with pytest.raises(ValueError):
        triage(ids, [], sample_rate=1.5)


def make_store(tmp_path):
    rows = [good_row(row_id=1, bar_mark="A"),
            good_row(row_id=2, bar_mark="B", total_weight_kg=90),
            good_row(row_id=3, bar_mark="C", shape_code="99"),
            good_row(row_id=4, bar_mark="D", cut_length_mm=4050, total_weight_kg=64.0)]
    findings = check_schedule(rows)
    routes = triage([1, 2, 3, 4], findings, sample_rate=1.0)
    store = Store(str(tmp_path / "qa.db"))
    store.save_run(rows, findings, routes)
    return store


def test_queue_decisions_and_metrics(tmp_path):
    store = make_store(tmp_path)
    assert [r["row_id"] for r in store.queue()] == [1, 3, 4]
    store.decide(3, "reviewer_a", "ok", "valid special shape")
    store.decide(4, "reviewer_a", "issue")
    store.decide(1, "reviewer_a", "ok")
    assert store.queue() == []
    m = store.metrics()
    assert m["routes"] == {AUTO_ACCEPT: 0, AUTO_FLAG: 1, HUMAN_REVIEW: 2, QA_SAMPLE: 1}
    assert m["automation_rate"] == 0.25
    assert m["human_review"]["false_alarm_rate"] == 0.5
    assert m["qa_sample"]["escape_rate"] == 0.0
    assert m["rules"]["unsupported_shape_code"]["false_alarm"] == 1
    assert m["rules"]["cut_length_deviation"]["confirmed"] == 1


def test_latest_decision_wins_but_history_is_kept(tmp_path):
    store = make_store(tmp_path)
    store.decide(3, "reviewer_a", "ok")
    store.decide(3, "reviewer_b", "issue", "second opinion")
    assert store.latest_decisions()[3]["decision"] == "issue"
    assert store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 2


def test_invalid_decisions_are_rejected(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(ValueError):
        store.decide(2, "reviewer_a", "ok")       # auto-flagged, not in queue
    with pytest.raises(ValueError):
        store.decide(99, "reviewer_a", "ok")      # unknown row
    with pytest.raises(ValueError):
        store.decide(3, "reviewer_a", "maybe")    # invalid decision
    with pytest.raises(ValueError):
        store.decide(3, " ", "ok")                # no reviewer name


def test_generator_is_reproducible_and_labelled():
    rows1, truth1 = generate(60, seed=7)
    rows2, truth2 = generate(60, seed=7)
    assert rows1 == rows2 and truth1 == truth2
    assert generate(60, seed=8)[0] != rows1
    injected = [t["injected_case"] for t in truth1 if t["injected_case"] != "none"]
    for case, (n, _) in CASES.items():
        assert injected.count(case) == (2 if case == "duplicate_mark" else n)
    with pytest.raises(ValueError):
        generate(10)


@pytest.mark.parametrize("seed", [1, 7, 42, 2026])
def test_no_injected_defect_is_auto_accepted(seed):
    rows, truth = generate(80, seed=seed)
    rows = [{k: str(v) for k, v in r.items()} for r in rows]
    routes = triage([int(r["row_id"]) for r in rows], check_schedule(rows), 0.1, seed)
    result = evaluate(routes, {t["row_id"]: bool(t["is_defect"]) for t in truth})
    assert result["defects_missed"] == []
    assert result["clean_rows_auto_flagged"] == 0


def test_cli_end_to_end(tmp_path, capsys):
    data, out, db = str(tmp_path / "data"), str(tmp_path / "out"), str(tmp_path / "qa.db")
    main(["generate", "--out-dir", data])
    main(["check", f"{data}/sample_bbs.csv", "--db", db, "--out-dir", out])
    main(["simulate-review", "--db", db, "--truth", f"{data}/sample_truth.csv",
          "--out", f"{out}/decisions.csv"])
    main(["import-decisions", f"{out}/decisions.csv", "--db", db])
    main(["report", "--db", db, "--out", f"{out}/report.md"])
    text = capsys.readouterr().out
    assert "Reviews still pending: 0" in text
    assert (tmp_path / "out" / "report.json").exists()


def test_cli_rejects_bad_input(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("row_id,bar_mark\n1,A\n")
    with pytest.raises(SystemExit):
        main(["check", str(bad), "--db", str(tmp_path / "qa.db")])
