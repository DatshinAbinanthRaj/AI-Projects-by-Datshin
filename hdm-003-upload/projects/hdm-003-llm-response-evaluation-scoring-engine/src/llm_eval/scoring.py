"""Combine human rubric ratings with automated checks into one result per response."""
from statistics import mean

from .checks import run_checks

PASS, FAIL = "PASS", "FAIL"
NEEDS_HUMAN, INCOMPLETE = "NEEDS_HUMAN_SCORES", "INCOMPLETE_SCORES"


def weighted_score(rubric, criterion_means):
    """Weighted rubric score on a 0-100 scale.

    Each criterion mean is first rescaled so the lowest rating is 0 and the
    highest is 1, then multiplied by its weight. Weights add up to 1.
    """
    span = rubric.scale_max - rubric.scale_min
    total = sum(c.weight * (criterion_means[c.id] - rubric.scale_min) / span
                for c in rubric.criteria)
    return round(100 * total, 2)


def score_response(rubric, case, response_text, human=None):
    """Score one response.

    `human` is {criterion_id: {evaluator: score}} or None.
    Verdict rules, all reasons are kept:
      FAIL  if an automated critical check fails,
            or a critical criterion's mean rating is below its minimum,
            or the weighted score is below the rubric pass mark.
      NEEDS_HUMAN_SCORES / INCOMPLETE_SCORES if ratings are missing and no
            automated critical check has already failed the response.
    """
    human = human or {}
    auto = run_checks(case, response_text)
    means = {cid: mean(by_eval.values()) for cid, by_eval in human.items() if by_eval}
    missing = [cid for cid in rubric.criterion_ids if cid not in means]
    evaluators = sorted({e for by_eval in human.values() for e in by_eval})

    reasons = list(auto["critical_failures"])
    flags = list(auto["warnings"])
    score = None

    if not missing:
        score = weighted_score(rubric, means)
        for c in rubric.criteria:
            if c.critical and means[c.id] < c.critical_min:
                reasons.append(f"low_critical:{c.id}")
        if score < rubric.pass_score:
            reasons.append("below_pass_score")

    for cid, by_eval in human.items():
        if len(by_eval) > 1 and max(by_eval.values()) - min(by_eval.values()) >= rubric.disagreement_gap:
            flags.append(f"evaluator_disagreement:{cid}")

    # Humans rated it well, but an objective check says otherwise: worth a second look.
    high = rubric.scale_max - 1
    link = rubric.auto_links.get("fact_coverage")
    if link in means and auto["fact_coverage"] is not None:
        if auto["fact_coverage"] <= 0.5 and means[link] >= high:
            flags.append(f"human_auto_mismatch:{link}")
    link = rubric.auto_links.get("forbidden_content")
    if link in means and auto["forbidden_hits"] and means[link] >= high:
        flags.append(f"human_auto_mismatch:{link}")

    if reasons:
        verdict = FAIL
    elif not means:
        verdict = NEEDS_HUMAN
    elif missing:
        verdict = INCOMPLETE
    else:
        verdict = PASS

    return {
        "verdict": verdict,
        "score": score,
        "reasons": reasons,
        "flags": sorted(flags),
        "criterion_means": {k: round(v, 2) for k, v in means.items()},
        "missing_criteria": missing,
        "evaluators": evaluators,
        "auto": auto,
    }


def score_all(rubric, cases, responses, human_scores):
    """Score every response. Returns a list of result dicts sorted by case and model."""
    results = []
    for (cid, model) in sorted(responses):
        result = score_response(rubric, cases[cid], responses[(cid, model)],
                                human_scores.get((cid, model)))
        result["case_id"], result["model"] = cid, model
        results.append(result)
    return results
