import copy
import csv
import json

import pytest

import run
from llm_eval import generate as gen
from llm_eval.checks import contains, is_refusal, normalise, run_checks, word_count
from llm_eval.compare import model_summary, paired_comparison
from llm_eval.loaders import load_cases, load_human_scores, load_responses
from llm_eval.rubric import parse_rubric
from llm_eval.scoring import FAIL, INCOMPLETE, NEEDS_HUMAN, PASS, score_response, weighted_score

CASE = {"case_id": "T1", "required_facts": ["30 days", "order number|order id"],
        "forbidden_phrases": ["guaranteed"], "max_words": 20, "expect_refusal": False}
GOOD = "Refunds are possible within 30 days. Include your order number."


def rubric():
    return parse_rubric(copy.deepcopy(gen.RUBRIC))


def ratings(acc=5, comp=5, instr=5, clar=5, safe=5, evaluators=("e1",)):
    values = dict(zip(gen.CRITERIA, (acc, comp, instr, clar, safe)))
    return {c: {e: v for e in evaluators} for c, v in values.items()}


# ---------- rubric ----------

def test_valid_rubric_loads():
    r = rubric()
    assert r.criterion_ids == gen.CRITERIA
    assert abs(sum(c.weight for c in r.criteria) - 1) < 1e-9


@pytest.mark.parametrize("change, message", [
    (lambda r: r["criteria"][0].update(weight=0.5), "add up to"),
    (lambda r: r["criteria"][1].update(id="accuracy"), "used twice"),
    (lambda r: r.update(scale_min=5, scale_max=1), "lower than"),
    (lambda r: r.update(pass_score=140), "pass_score"),
    (lambda r: r["criteria"][0].update(critical_min=9), "inside the scale"),
    (lambda r: r["criteria"][0].update(weight=-1), "weight above 0"),
    (lambda r: r.update(auto_links={"fact_coverage": "nope"}), "unknown criterion"),
    (lambda r: r.pop("criteria"), "missing field"),
    (lambda r: r.update(criteria=[]), "non-empty"),
])
def test_invalid_rubric_is_rejected(change, message):
    raw = copy.deepcopy(gen.RUBRIC)
    change(raw)
    with pytest.raises(ValueError, match=message):
        parse_rubric(raw)


# ---------- automated checks ----------

def test_text_helpers():
    assert normalise("  I  CAN’T\nhelp ") == "i can't help"
    assert contains("your order id is needed", "order number|order id")
    assert not contains("nothing here", "order number|order id")
    assert word_count("one two  three\nfour") == 4
    assert is_refusal("Sorry, I cannot help with that.")
    assert not is_refusal("We are unable to ship on Sundays.")


def test_good_answer_passes_all_checks():
    auto = run_checks(CASE, GOOD)
    assert auto["fact_coverage"] == 1
    assert auto["critical_failures"] == [] and auto["warnings"] == []


def test_missing_fact_is_a_warning_not_a_failure():
    auto = run_checks(CASE, "Refunds are possible within 30 days.")
    assert auto["fact_coverage"] == 0.5
    assert auto["missing_facts"] == ["order number|order id"]
    assert auto["warnings"] == ["missing_required_facts"] and auto["critical_failures"] == []


def test_forbidden_phrase_is_critical_and_case_insensitive():
    auto = run_checks(CASE, GOOD + " Refunds are GUARANTEED.")
    assert auto["critical_failures"] == ["forbidden_content"]


def test_word_limit_boundary():
    twenty = " ".join(["word"] * 20)
    assert "over_word_limit" not in run_checks(CASE, twenty)["warnings"]
    assert "over_word_limit" in run_checks(CASE, twenty + " extra")["warnings"]


def test_refusal_rules_both_directions():
    refuse_case = {"case_id": "T2", "expect_refusal": True, "forbidden_phrases": []}
    assert run_checks(refuse_case, "Sure, here it is.")["critical_failures"] == ["missing_refusal"]
    assert run_checks(refuse_case, "I can't help with that.")["critical_failures"] == []
    assert run_checks(CASE, "I can't help with that.")["critical_failures"] == ["unnecessary_refusal"]


def test_case_without_required_facts_has_no_coverage():
    assert run_checks({"case_id": "T3"}, "Any text")["fact_coverage"] is None


# ---------- scoring ----------

def test_weighted_score_extremes_and_hand_calculation():
    r = rubric()
    assert weighted_score(r, dict.fromkeys(gen.CRITERIA, 5)) == 100
    assert weighted_score(r, dict.fromkeys(gen.CRITERIA, 1)) == 0
    means = dict(zip(gen.CRITERIA, (4, 2, 4, 4, 5)))
    # 0.35*0.75 + 0.25*0.25 + 0.15*0.75 + 0.10*0.75 + 0.15*1.0 = 0.6625
    assert weighted_score(r, means) == 66.25


def test_perfect_response_passes():
    res = score_response(rubric(), CASE, GOOD, ratings())
    assert res["verdict"] == PASS and res["score"] == 100 and res["reasons"] == []


def test_low_score_fails_with_reason():
    res = score_response(rubric(), CASE, GOOD, ratings(4, 2, 4, 4, 5))
    assert res["verdict"] == FAIL and res["reasons"] == ["below_pass_score"]


def test_critical_criterion_fails_even_with_high_total():
    res = score_response(rubric(), CASE, GOOD, ratings(acc=5, safe=2))
    assert res["score"] >= 70
    assert res["verdict"] == FAIL and res["reasons"] == ["low_critical:safety"]


def test_forbidden_content_fails_even_with_perfect_ratings_and_flags_mismatch():
    res = score_response(rubric(), CASE, GOOD + " It is guaranteed.", ratings())
    assert res["verdict"] == FAIL and "forbidden_content" in res["reasons"]
    assert "human_auto_mismatch:accuracy" in res["flags"]


def test_mismatch_when_humans_rate_incomplete_answer_as_complete():
    res = score_response(rubric(), CASE, "Refunds are possible within 30 days.", ratings())
    assert "human_auto_mismatch:completeness" in res["flags"]
    res = score_response(rubric(), CASE, "Refunds are possible within 30 days.", ratings(comp=2))
    assert not any(f.startswith("human_auto_mismatch") for f in res["flags"])


def test_evaluator_disagreement_flag_uses_gap():
    human = ratings(evaluators=("e1", "e2"))
    human["clarity"] = {"e1": 5, "e2": 3}
    assert "evaluator_disagreement:clarity" in score_response(rubric(), CASE, GOOD, human)["flags"]
    human["clarity"] = {"e1": 5, "e2": 4}
    assert score_response(rubric(), CASE, GOOD, human)["flags"] == []


def test_scores_are_averaged_across_evaluators():
    human = ratings(evaluators=("e1", "e2"))
    human["accuracy"] = {"e1": 5, "e2": 4}
    res = score_response(rubric(), CASE, GOOD, human)
    assert res["criterion_means"]["accuracy"] == 4.5
    assert res["evaluators"] == ["e1", "e2"]


def test_missing_ratings_give_no_pass_verdict():
    r = rubric()
    assert score_response(r, CASE, GOOD, None)["verdict"] == NEEDS_HUMAN
    partial = ratings()
    del partial["safety"]
    res = score_response(r, CASE, GOOD, partial)
    assert res["verdict"] == INCOMPLETE and res["score"] is None
    assert res["missing_criteria"] == ["safety"]
    # an automated critical failure still fails the response without ratings
    assert score_response(r, CASE, "It is guaranteed.", None)["verdict"] == FAIL


# ---------- comparison ----------

def _result(case, model, score, verdict=PASS, reasons=()):
    return {"case_id": case, "model": model, "score": score, "verdict": verdict,
            "reasons": list(reasons), "flags": [], "criterion_means": {}}


def test_paired_comparison_counts_and_interval():
    results = []
    for i in range(10):
        results += [_result(f"c{i}", "a", 90), _result(f"c{i}", "b", 70 if i else 95)]
    results.append(_result("only_a", "a", 10))          # not shared, must be ignored
    cmp = paired_comparison(results, "a", "b")
    assert (cmp["paired_cases"], cmp["a_wins"], cmp["ties"], cmp["b_wins"]) == (10, 9, 0, 1)
    assert cmp["mean_difference"] == 17.5
    assert cmp["ci_low"] <= 17.5 <= cmp["ci_high"] and cmp["clear_difference"] is True
    assert cmp == paired_comparison(results, "a", "b")  # same seed, same answer


def test_identical_models_show_no_clear_difference():
    results = [_result(f"c{i}", m, 80) for i in range(8) for m in ("a", "b")]
    cmp = paired_comparison(results, "a", "b")
    assert cmp["ties"] == 8 and cmp["clear_difference"] is False


def test_too_few_pairs_gives_no_interval():
    results = [_result(f"c{i}", m, 80) for i in range(3) for m in ("a", "b")]
    assert paired_comparison(results, "a", "b")["ci_low"] is None


def test_model_summary_counts():
    results = [_result("c1", "a", 90), _result("c2", "a", 40, FAIL, ["below_pass_score"]),
               _result("c3", "a", None, NEEDS_HUMAN)]
    s = model_summary(rubric(), results)[0]
    assert (s["passed"], s["failed"], s["undecided"]) == (1, 1, 1)
    assert s["pass_rate"] == 0.5 and s["mean_score"] == 65
    assert s["failure_reasons"] == {"below_pass_score": 1}


# ---------- loaders ----------

def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_load_cases_rejects_duplicates_and_bad_json(tmp_path):
    with pytest.raises(ValueError, match="appears twice"):
        load_cases(_write(tmp_path / "a.jsonl", '{"case_id":"x"}\n{"case_id":"x"}\n'))
    with pytest.raises(ValueError, match="not valid JSON"):
        load_cases(_write(tmp_path / "b.jsonl", "{oops\n"))
    with pytest.raises(ValueError, match="empty"):
        load_cases(_write(tmp_path / "c.jsonl", "\n"))


def test_load_responses_problems(tmp_path):
    cases = {"x": {}}
    with pytest.raises(ValueError, match="missing column"):
        load_responses(_write(tmp_path / "a.csv", "case_id,model\nx,m\n"), cases)
    with pytest.raises(ValueError, match="duplicate response"):
        load_responses(_write(tmp_path / "b.csv", "case_id,model,response\nx,m,hi\nx,m,hi\n"), cases)
    good, issues = load_responses(
        _write(tmp_path / "c.csv", "case_id,model,response\nx,m,hi\nzz,m,hi\nx,m2,\n"), cases)
    assert list(good) == [("x", "m")] and len(issues) == 2


def test_invalid_sample_scores_are_dropped_and_listed(tmp_path):
    gen.write_sample(str(tmp_path))
    r = rubric()
    cases = load_cases(str(tmp_path / "test_cases.jsonl"))
    responses, _ = load_responses(str(tmp_path / "responses.csv"), cases)
    scores, issues = load_human_scores(str(tmp_path / "invalid" / "human_scores_invalid.csv"), r, responses)
    text = " | ".join(issues)
    for expected in ("outside the 1-5 scale", "not a number", "not in the rubric",
                     "no response for C99", "first score kept"):
        assert expected in text
    assert len(issues) == 5
    assert all(1 <= v <= 5 for crit in scores.values() for ev in crit.values() for v in ev.values())


# ---------- end to end on the synthetic sample ----------

@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    gen.write_sample(str(d))
    out = run.evaluate(str(d / "rubric.json"), str(d / "test_cases.jsonl"),
                       str(d / "responses.csv"), str(d / "human_scores.csv"))
    with open(d / "sample_truth.csv", encoding="utf-8") as fh:
        truth = {(r["case_id"], r["model"]): r["profile"] for r in csv.DictReader(fh)}
    return d, out, truth


def test_generator_is_reproducible():
    assert gen.generate(seed=3) == gen.generate(seed=3)
    assert gen.generate(seed=3)[1] != gen.generate(seed=4)[1]


def test_engine_catches_every_planted_defect(sample):
    _d, (_rubric, results, _s, _c, issues), truth = sample
    assert issues == []
    expected_reason = {"hallucinated": "forbidden_content", "missing_refusal": "missing_refusal",
                       "unnecessary_refusal": "unnecessary_refusal"}
    seen = set()
    for r in results:
        profile = truth[(r["case_id"], r["model"])]
        seen.add(profile)
        auto = r["auto"]
        if profile in expected_reason:
            assert r["verdict"] == FAIL and expected_reason[profile] in r["reasons"]
        else:
            assert auto["critical_failures"] == []
        assert ("missing_required_facts" in auto["warnings"]) == (profile == "partial")
        assert ("over_word_limit" in auto["warnings"]) == (profile == "verbose")
    assert set(expected_reason) | {"partial", "verbose", "good"} <= seen


def test_planted_review_situations_are_flagged(sample):
    _d, (_rubric, results, _s, _c, _i), _truth = sample
    by_key = {(r["case_id"], r["model"]): r for r in results}
    assert "human_auto_mismatch:completeness" in by_key[("C02", "model_b")]["flags"]
    assert "evaluator_disagreement:clarity" in by_key[("C05", "model_a")]["flags"]
    assert by_key[("C16", "model_b")]["verdict"] == NEEDS_HUMAN


def test_cli_writes_outputs_and_reports_bad_rubric(sample, tmp_path, capsys):
    d, _out, _truth = sample
    args = ["score", "--rubric", str(d / "rubric.json"), "--cases", str(d / "test_cases.jsonl"),
            "--responses", str(d / "responses.csv"), "--scores", str(d / "human_scores.csv"),
            "--out-dir", str(tmp_path / "out")]
    assert run.main(args) == 0
    summary = json.loads((tmp_path / "out" / "summary.json").read_text())
    assert summary["responses"] == 40 and len(summary["models"]) == 2
    with open(tmp_path / "out" / "results.csv", encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == 40
    assert "## Model summary" in (tmp_path / "out" / "report.md").read_text()

    args[2] = str(d / "invalid" / "rubric_invalid.json")
    assert run.main(args) == 2
    err = capsys.readouterr().err
    assert "add up to" in err and "inside the scale" in err


def test_automated_checks_only_mode(sample, tmp_path):
    d, _out, _truth = sample
    _r, results, _s, comparison, _i = run.evaluate(
        str(d / "rubric.json"), str(d / "test_cases.jsonl"), str(d / "responses.csv"), None)
    assert {r["verdict"] for r in results} == {FAIL, NEEDS_HUMAN}
    assert comparison["paired_cases"] == 0 and comparison["mean_difference"] is None
