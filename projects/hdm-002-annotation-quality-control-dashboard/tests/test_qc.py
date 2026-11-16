import json
import os

import pandas as pd
import pytest

import run
from annotation_qc import generate as gen
from annotation_qc.qc import (Thresholds, analyse, annotator_metrics, batch_metrics, confusion,
                              item_table, pairwise, validate, wilson_interval)
from annotation_qc.report import to_markdown

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "..", "data")
LABELS = ["billing", "technical", "account", "other"]
COLS = ["item_id", "annotator_id", "label", "gold_label", "batch", "seconds_spent"]


def frame(rows):
    return pd.DataFrame(rows, columns=COLS)


def small():
    # 2 items, 3 annotators. a is always right, c is always wrong on gold.
    return frame([
        ["i1", "a", "x", "x", "B1", 30], ["i1", "b", "x", "x", "B1", 30], ["i1", "c", "y", "x", "B1", 3],
        ["i2", "a", "y", "y", "B2", 30], ["i2", "b", "y", "y", "B2", 30], ["i2", "c", "x", "y", "B2", 3],
    ])


# ---- Wilson interval
def test_wilson_known_value():
    low, high = wilson_interval(8, 10)
    assert low == pytest.approx(0.4902, abs=1e-3)
    assert high == pytest.approx(0.9433, abs=1e-3)


def test_wilson_zero_n_and_bounds():
    assert wilson_interval(0, 0) == (0.0, 1.0)
    low, high = wilson_interval(10, 10)
    assert 0 < low < 1 and high == pytest.approx(1.0)


def test_wilson_narrows_with_more_data():
    a = wilson_interval(8, 10)
    b = wilson_interval(80, 100)
    assert (b[1] - b[0]) < (a[1] - a[0])


# ---- validation
def test_missing_column_raises():
    with pytest.raises(ValueError, match="gold_label"):
        validate(small().drop(columns="gold_label"))


def test_invalid_sample_file_issues():
    raw = pd.read_csv(os.path.join(DATA, "sample_invalid.csv"), dtype=str, keep_default_na=False)
    clean, issues = validate(raw, LABELS)
    texts = [i["issue"] for i in issues]
    assert sum("twice" in t for t in texts) == 1
    assert sum("allowed label set" in t for t in texts) == 1
    assert sum("blank" in t for t in texts) == 2
    assert sum("seconds_spent" in t for t in texts) == 2
    assert sum("more than one gold" in t for t in texts) == 1
    assert len(clean) == 11 - 4                      # four rows dropped
    assert (clean[clean["item_id"] == "X004"]["gold_label"] == "").all()


def test_gold_label_spreads_to_all_rows_of_item():
    clean, _ = validate(pd.read_csv(os.path.join(DATA, "sample_invalid.csv"), dtype=str,
                                    keep_default_na=False), LABELS)
    assert (clean[clean["item_id"] == "X001"]["gold_label"] == "billing").all()


def test_validation_reports_spreadsheet_row_number():
    _, issues = validate(frame([["i1", "a", "x", "", "B1", 5], ["i2", "", "x", "", "B1", 5]]))
    assert issues[0]["row"] == 3  # header is row 1


def test_clean_data_has_no_issues():
    _, issues = validate(small())
    assert issues == []


# ---- agreement
def test_pairwise_counts_and_values():
    p = pairwise(validate(small())[0])
    assert len(p) == 6                 # 3 pairs per item
    assert p["agree"].sum() == 2       # only a-b agree


def test_single_annotator_item_has_no_pairs():
    p = pairwise(validate(frame([["i1", "a", "x", "", "B1", 5]]))[0])
    assert p.empty


def test_item_table_disputed_and_tie():
    df = validate(frame([["i1", "a", "x", "", "B1", 5], ["i1", "b", "y", "", "B1", 5],
                         ["i2", "a", "x", "", "B1", 5], ["i2", "b", "x", "", "B1", 5]]))[0]
    t = item_table(df).set_index("item_id")
    assert t.loc["i1", "disputed"] and t.loc["i1", "majority_label"] == ""
    assert not t.loc["i2", "disputed"] and t.loc["i2", "majority_label"] == "x"


# ---- annotator metrics and flags
def test_accuracy_and_agreement_numbers():
    m = annotator_metrics(validate(small())[0]).set_index("annotator_id")
    assert m.loc["a", "gold_accuracy"] == 1.0
    assert m.loc["c", "gold_accuracy"] == 0.0
    assert m.loc["a", "agreement_rate"] == pytest.approx(0.5)
    assert m.loc["c", "agreement_rate"] == 0.0


def test_flags_respect_minimum_sample():
    df = validate(small())[0]
    strict = annotator_metrics(df, Thresholds(min_gold=1, min_pairs=1)).set_index("annotator_id")
    assert "LOW_GOLD_ACCURACY" in strict.loc["c", "flags"]
    assert "LOW_AGREEMENT" in strict.loc["c", "flags"]
    default = annotator_metrics(df).set_index("annotator_id")
    assert "LOW_GOLD_ACCURACY" not in default.loc["c", "flags"]
    assert "accuracy not judged" in default.loc["c", "notes"]


def test_too_fast_flag():
    m = annotator_metrics(validate(small())[0]).set_index("annotator_id")
    assert "TOO_FAST" in m.loc["c", "flags"]
    assert "TOO_FAST" not in m.loc["a", "flags"]


def test_label_bias_flag():
    rows = []
    for i in range(20):
        rows.append([f"i{i}", "a", "x" if i % 2 else "y", "", "B1", 10])
        rows.append([f"i{i}", "b", "x", "", "B1", 10])   # b always says x
    m = annotator_metrics(validate(frame(rows))[0]).set_index("annotator_id")
    assert m.loc["b", "label_bias"] == pytest.approx(0.5)
    assert "LABEL_BIAS" in m.loc["b", "flags"]


def test_evidence_strength():
    rows = [[f"i{i}", "a", "x" if i < 2 else "y", "x", "B1", 10] for i in range(40)]   # 2/40 correct
    rows += [[f"j{i}", "b", "x" if i < 9 else "y", "x", "B1", 10] for i in range(12)]  # 9/12 correct
    m = annotator_metrics(validate(frame(rows))[0]).set_index("annotator_id")
    assert m.loc["a", "accuracy_evidence"] == "strong"
    assert m.loc["b", "accuracy_evidence"] == "weak"


def test_no_gold_at_all():
    res = analyse(frame([["i1", "a", "x", "", "B1", 5], ["i1", "b", "x", "", "B1", 5]]))
    assert res["summary"]["gold_accuracy"] is None
    assert res["confusion"].empty
    assert "n/a" in to_markdown(res)


# ---- batches and confusion
def test_batch_metrics():
    b = batch_metrics(validate(small())[0]).set_index("batch")
    assert b.loc["B1", "gold_accuracy"] == pytest.approx(2 / 3)
    assert b.loc["B1", "agreement_rate"] == pytest.approx(1 / 3)


def test_confusion_totals():
    c = confusion(validate(small())[0])
    assert c.loc["x", "x"] == 2 and c.loc["x", "y"] == 1
    assert c.values.sum() == 6


# ---- synthetic sample: planted problems are found
def test_generator_is_reproducible_and_matches_committed_file():
    a, b = gen.generate(seed=11), gen.generate(seed=11)
    assert a.equals(b)
    committed = pd.read_csv(os.path.join(DATA, "sample_annotations.csv"), keep_default_na=False)
    assert committed.astype(str).equals(a.astype(str))


def test_planted_problems_are_flagged_on_sample():
    res = analyse(gen.generate(seed=11), allowed_labels=LABELS)
    m = res["annotators"].set_index("annotator_id")
    assert "TOO_FAST" in m.loc["ann_e", "flags"]
    assert "LOW_GOLD_ACCURACY" in m.loc["ann_d", "flags"]
    assert m.loc["ann_a", "flags"] == "" and m.loc["ann_b", "flags"] == ""
    assert res["summary"]["rows_used"] == 360
    b = res["batches"].set_index("batch")
    assert b.loc["B4", "agreement_rate"] == b["agreement_rate"].min()


# ---- CLI
def test_cli_check_writes_outputs(tmp_path, capsys):
    code = run.main(["check", os.path.join(DATA, "sample_annotations.csv"), "--out-dir", str(tmp_path)])
    assert code == 1  # flagged annotators exist
    for name in ["report.md", "summary.json", "annotators.csv", "disputed_items.csv", "validation_issues.csv"]:
        assert (tmp_path / name).exists()
    summary = json.loads((tmp_path / "summary.json").read_text())["summary"]
    assert summary["items"] == 120 and summary["gold_items"] == 36
    assert "Annotation quality report" in capsys.readouterr().out


def test_cli_bad_file_returns_2(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("item_id,label\n1,x\n")
    assert run.main(["check", str(bad), "--out-dir", str(tmp_path)]) == 2
    assert "Missing required column" in capsys.readouterr().err
    assert run.main(["check", str(tmp_path / "nope.csv")]) == 2
