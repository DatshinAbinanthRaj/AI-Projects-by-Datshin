import csv
import json
import os

import pytest

import run
from agreement import analysis, generate, loaders, metrics

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")


def wide(*columns):
    """Build units from one list per annotator; None means 'not rated'."""
    units = {}
    for a, column in enumerate(columns):
        for i, value in enumerate(column):
            units.setdefault(i, {})
            if value is not None:
                units[i][f"r{a}"] = value
    return units


# ---- published reference values -------------------------------------------------

# Krippendorff (2011), "Computing Krippendorff's Alpha-Reliability": 4 observers, 12 units.
_ = None
KRIPP = wide(
    [1, 2, 3, 3, 2, 1, 4, 1, 2, _, _, _],
    [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, _, 3],
    [_, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, _],
    [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, _],
)


def test_alpha_nominal_matches_published_example():
    assert metrics.krippendorff_alpha(KRIPP, "nominal") == pytest.approx(0.743, abs=0.0005)


def test_alpha_ordinal_matches_published_example():
    assert metrics.krippendorff_alpha(KRIPP, "ordinal", [1, 2, 3, 4, 5]) == pytest.approx(0.815, abs=0.0005)


def test_alpha_interval_matches_published_example():
    assert metrics.krippendorff_alpha(KRIPP, "interval") == pytest.approx(0.849, abs=0.0005)


# Fleiss (1971) worked example: 10 subjects, 14 raters, 5 categories, kappa = 0.210.
FLEISS_COUNTS = [
    [0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1],
    [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7],
]


def test_fleiss_kappa_matches_published_example():
    units = {}
    for i, row in enumerate(FLEISS_COUNTS):
        labels = [c for c, n in enumerate(row) for _ in range(n)]
        units[i] = {f"r{j}": label for j, label in enumerate(labels)}
    kappa, items, m = metrics.fleiss_kappa(units)
    assert (items, m) == (10, 14)
    assert kappa == pytest.approx(0.210, abs=0.0005)


# ---- hand-calculated small cases ------------------------------------------------

def test_cohen_kappa_hand_calculated():
    # 2x2 table: both yes 20, a yes/b no 5, a no/b yes 10, both no 15. n = 50.
    # observed = 35/50 = 0.70; expected = (25*30 + 25*20)/2500 = 0.50; kappa = 0.40
    a = ["y"] * 25 + ["n"] * 25
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    kappa, raw, n = metrics.cohen_kappa(wide(a, b), "r0", "r1")
    assert n == 50
    assert raw == pytest.approx(0.70)
    assert kappa == pytest.approx(0.40)


def test_perfect_agreement_gives_one():
    units = wide(["a", "b", "c", "a"], ["a", "b", "c", "a"], ["a", "b", "c", "a"])
    assert metrics.percent_agreement(units) == 1
    assert metrics.krippendorff_alpha(units) == pytest.approx(1)
    assert metrics.fleiss_kappa(units)[0] == pytest.approx(1)
    assert metrics.cohen_kappa(units, "r0", "r1")[0] == pytest.approx(1)


def test_single_label_is_undefined_not_a_crash():
    units = wide(["a", "a", "a"], ["a", "a", "a"])
    assert metrics.percent_agreement(units) == 1
    assert metrics.krippendorff_alpha(units) is None
    assert metrics.fleiss_kappa(units)[0] is None
    assert metrics.cohen_kappa(units, "r0", "r1")[0] is None
    assert analysis.band(None) == "undefined"


def test_systematic_disagreement_is_below_zero():
    units = wide(["a", "b", "a", "b"], ["b", "a", "b", "a"])
    assert metrics.krippendorff_alpha(units) < 0
    assert metrics.cohen_kappa(units, "r0", "r1")[0] == pytest.approx(-1)


def test_percent_agreement_counts_pairs():
    # item 0: a,a,b -> 1 of 3 pairs match; item 1: a,a -> 1 of 1. Total 2 of 4.
    units = {0: {"x": "a", "y": "a", "z": "b"}, 1: {"x": "a", "y": "a"}}
    assert metrics.percent_agreement(units) == pytest.approx(0.5)


def test_items_with_one_rating_do_not_change_alpha():
    extra = dict(KRIPP)
    extra["solo"] = {"r0": 5}
    assert metrics.krippendorff_alpha(extra) == pytest.approx(metrics.krippendorff_alpha(KRIPP))


def test_alpha_two_raters_no_missing_close_to_kappa():
    a = ["y"] * 25 + ["n"] * 25
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    alpha = metrics.krippendorff_alpha(wide(a, b))
    assert alpha == pytest.approx(0.40, abs=0.02)


def test_ordinal_rewards_near_misses():
    near = wide([1, 2, 3, 4, 5, 1, 2, 3, 4, 5], [2, 3, 4, 5, 4, 1, 2, 3, 4, 5])
    order = [1, 2, 3, 4, 5]
    assert metrics.krippendorff_alpha(near, "ordinal", order) > metrics.krippendorff_alpha(near, "nominal")


def test_ordinal_needs_complete_order():
    with pytest.raises(ValueError, match="missing from the order"):
        metrics.krippendorff_alpha(KRIPP, "ordinal", [1, 2, 3])
    with pytest.raises(ValueError, match="needs"):
        analysis.analyse(KRIPP, "ordinal", None, reps=0)


def test_fleiss_uses_only_items_with_the_common_rating_count():
    units = wide(["a", "b", "a", "b"], ["a", "b", "b", "b"], ["a", "b", "a", None])
    _, items, m = metrics.fleiss_kappa(units)
    assert (items, m) == (3, 3)


# ---- analysis tables ------------------------------------------------------------

def test_bands():
    assert analysis.band(0.85) == "reliable"
    assert analysis.band(0.80) == "reliable"
    assert analysis.band(0.70) == "tentative"
    assert analysis.band(0.50) == "unreliable"


def test_bootstrap_is_repeatable_and_contains_alpha():
    low1, high1 = analysis.bootstrap_alpha(KRIPP, "nominal", None, reps=300, seed=3)
    low2, high2 = analysis.bootstrap_alpha(KRIPP, "nominal", None, reps=300, seed=3)
    assert (low1, high1) == (low2, high2)
    assert low1 < 0.743 < high1


def test_removing_the_noisy_annotator_raises_alpha():
    good = ["a", "b", "c", "a", "b", "c", "a", "b", "c", "a", "b", "c"]
    noisy = ["b", "c", "a", "a", "c", "c", "b", "b", "a", "c", "b", "a"]
    res = analysis.analyse(wide(good, good, good, noisy), reps=0, min_overlap=5)
    by = {r["annotator"]: r for r in res["annotators"]}
    assert by["r3"]["alpha_change_if_removed"] > 0.3
    assert by["r3"]["alpha_without_annotator"] == pytest.approx(1)
    assert by["r0"]["alpha_change_if_removed"] < 0
    assert by["r3"]["mean_kappa_with_others"] < by["r0"]["mean_kappa_with_others"]


def test_confusion_pairs_and_item_ranking():
    units = {
        "i1": {"x": "cat", "y": "dog"}, "i2": {"x": "cat", "y": "dog"},
        "i3": {"x": "cat", "y": "fish"}, "i4": {"x": "cat", "y": "cat"},
        "i5": {"x": "cat", "y": "cat", "z": "dog"},
    }
    res = analysis.analyse(units, reps=0)
    top = res["confusions"][0]
    assert (top["label_1"], top["label_2"]) == ("cat", "dog")
    assert sum(c["share_of_disagreement"] for c in res["confusions"]) == pytest.approx(1)
    assert res["items"][-1]["item_id"] == "i4"            # full agreement sorts last
    i5 = next(r for r in res["items"] if r["item_id"] == "i5")
    assert i5["majority_label"] == "cat"
    assert i5["item_agreement"] == pytest.approx(1 / 3)
    assert res["items"][0]["majority_label"] == ""          # a 1-1 split has no majority
    assert res["summary"]["items_with_any_disagreement"] == 4


def test_label_table_one_vs_rest():
    units = wide(["a", "a", "b", "c", "b", "c"], ["a", "a", "c", "b", "b", "c"])
    rows = {r["label"]: r for r in analysis.analyse(units, reps=0)["labels"]}
    assert rows["a"]["alpha_one_vs_rest"] == pytest.approx(1)   # 'a' is never confused
    assert rows["b"]["alpha_one_vs_rest"] < 1
    assert rows["a"]["times_used"] == 4


def test_low_overlap_pairs_are_marked_and_left_out_of_the_mean():
    units = wide(["a", "b", "a"], ["a", "b", "b"])
    res = analysis.analyse(units, reps=0, min_overlap=10)
    assert res["pairs"][0]["enough_overlap"] is False
    assert res["annotators"][0]["mean_kappa_with_others"] is None


def test_interval_needs_numbers():
    with pytest.raises(ValueError, match="numeric"):
        analysis.analyse(wide(["a", "b"], ["a", "b"]), "interval", reps=0)


def test_no_overlap_is_an_error():
    with pytest.raises(ValueError, match="two or more"):
        analysis.analyse({"i1": {"x": "a"}, "i2": {"y": "b"}}, reps=0)


# ---- loading and validation -----------------------------------------------------

def test_long_file_problems_are_listed():
    units, issues = loaders.load_ratings(os.path.join(DATA, "invalid", "problems_long.csv"),
                                         allowed=["cat", "dog"])
    problems = " | ".join(i["problem"] for i in issues)
    assert "ann_b rated i1 more than once ('cat' then 'dog')" in problems
    assert "unknown label 'fish'" in problems
    assert "blank annotator_id" in problems
    assert "item i2 has one rating only" in problems
    assert units["i1"] == {"ann_a": "cat", "ann_b": "cat"}       # first rating kept
    assert units["i4"] == {"ann_a": "cat", "ann_b": "dog"}


def test_missing_columns_and_bad_layout(tmp_path):
    with pytest.raises(ValueError, match="missing column"):
        loaders.load_ratings(os.path.join(DATA, "invalid", "missing_columns.csv"), layout="long")
    with pytest.raises(ValueError, match="wide layout needs"):
        loaders.load_ratings(os.path.join(DATA, "invalid", "missing_columns.csv"))
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    with pytest.raises(ValueError, match="empty"):
        loaders.load_ratings(str(empty))


def test_wide_and_long_layouts_give_the_same_units(tmp_path):
    w = tmp_path / "w.csv"
    w.write_text("item_id,a,b,c\ni1,x,y,\ni2,x,x,y\ni2,y,y,y\n")
    lg = tmp_path / "l.csv"
    lg.write_text("item_id,annotator_id,label\ni1,a,x\ni1,b,y\ni2,a,x\ni2,b,x\ni2,c,y\n")
    wide_units, wide_issues = loaders.load_ratings(str(w))
    long_units, _ = loaders.load_ratings(str(lg))
    assert wide_units == long_units
    assert any("appears twice" in i["problem"] for i in wide_issues)


# ---- sample data and command line -----------------------------------------------

def test_committed_samples_equal_generator_output(tmp_path):
    generate.write_all(str(tmp_path))
    for name in ("moderation_long.csv", "moderation_truth.csv", "quality_wide.csv", "skewed_two_raters.csv"):
        with open(tmp_path / name) as new, open(os.path.join(DATA, name)) as old:
            assert new.read() == old.read(), name


def test_planted_problems_are_found_in_the_moderation_sample():
    units, issues = loaders.load_ratings(os.path.join(DATA, "moderation_long.csv"))
    assert issues == []
    res = analysis.analyse(units, reps=200)
    top = res["confusions"][0]
    assert {top["label_1"], top["label_2"]} == {"spam", "misinformation"}
    worst = max(res["annotators"], key=lambda r: r["alpha_change_if_removed"])
    assert worst["annotator"] == "ann_5"
    assert res["summary"]["band"] == "unreliable"


def test_ordinal_alpha_beats_nominal_on_the_quality_sample():
    units, _ = loaders.load_ratings(os.path.join(DATA, "quality_wide.csv"))
    res = analysis.analyse(units, "ordinal", ["1", "2", "3", "4", "5"], reps=200)
    s = res["summary"]
    assert s["krippendorff_alpha"] > s["alpha_nominal"] + 0.3
    worst = max(res["annotators"], key=lambda r: r["alpha_change_if_removed"])
    assert worst["annotator"] == "rater_d"


def test_skewed_sample_high_raw_agreement_lower_kappa():
    units, _ = loaders.load_ratings(os.path.join(DATA, "skewed_two_raters.csv"))
    kappa, raw, _n = metrics.cohen_kappa(units, "rater_x", "rater_y")
    assert raw >= 0.95
    assert kappa < raw - 0.2


def test_cli_exit_codes_and_files(tmp_path, capsys):
    out = str(tmp_path / "out")
    assert run.main(["analyse", os.path.join(DATA, "moderation_long.csv"), "--out-dir", out,
                     "--bootstrap", "100"]) == 1
    for name in ("report.md", "summary.json", "pairwise.csv", "annotators.csv", "labels.csv",
                 "items_to_adjudicate.csv"):
        assert os.path.exists(os.path.join(out, name)), name
    with open(os.path.join(out, "summary.json")) as handle:
        assert json.load(handle)["summary"]["annotators"] == 5
    with open(os.path.join(out, "pairwise.csv")) as handle:
        assert len(list(csv.DictReader(handle))) == 10
    assert run.main(["analyse", os.path.join(DATA, "quality_wide.csv"), "--level", "ordinal",
                     "--order", "1,2,3,4,5", "--out-dir", out, "--bootstrap", "100"]) == 0
    assert run.main(["analyse", os.path.join(DATA, "invalid", "missing_columns.csv"), "--layout", "long",
                     "--out-dir", out]) == 2
    assert run.main(["analyse", "no_such_file.csv", "--out-dir", out]) == 2
    assert "ERROR" in capsys.readouterr().err
