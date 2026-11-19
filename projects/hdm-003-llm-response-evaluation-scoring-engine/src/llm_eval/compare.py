"""Summarise each model and compare two models on the cases they share."""
import random
from collections import Counter
from statistics import mean

from .scoring import FAIL, PASS


def model_summary(rubric, results):
    """One summary dict per model."""
    out = []
    for model in sorted({r["model"] for r in results}):
        rows = [r for r in results if r["model"] == model]
        decided = [r for r in rows if r["verdict"] in (PASS, FAIL)]
        scored = [r for r in rows if r["score"] is not None]
        passed = sum(r["verdict"] == PASS for r in rows)
        reasons = Counter(reason for r in rows if r["verdict"] == FAIL for reason in r["reasons"])
        crit_means = {}
        for cid in rubric.criterion_ids:
            values = [r["criterion_means"][cid] for r in rows if cid in r["criterion_means"]]
            crit_means[cid] = round(mean(values), 2) if values else None
        out.append({
            "model": model,
            "responses": len(rows),
            "decided": len(decided),
            "passed": passed,
            "failed": len(decided) - passed,
            "undecided": len(rows) - len(decided),
            "pass_rate": round(passed / len(decided), 4) if decided else None,
            "mean_score": round(mean(r["score"] for r in scored), 2) if scored else None,
            "criterion_means": crit_means,
            "failure_reasons": dict(sorted(reasons.items())),
            "flagged_for_review": sum(
                any(f.startswith(("human_auto_mismatch", "evaluator_disagreement")) for f in r["flags"])
                for r in rows),
        })
    return out


def paired_comparison(results, model_a, model_b, n_boot=2000, seed=7, min_pairs=5):
    """Compare two models on the cases where both have a rubric score.

    Returns wins, ties, losses and the mean score difference (A minus B) with a
    95% bootstrap interval: the cases are resampled with replacement many times
    and the middle 95% of the resulting mean differences is reported. If the
    interval includes 0, the data does not clearly separate the two models.
    """
    by_key = {(r["case_id"], r["model"]): r["score"] for r in results if r["score"] is not None}
    cases = sorted({c for (c, m) in by_key if m == model_a} & {c for (c, m) in by_key if m == model_b})
    diffs = [by_key[(c, model_a)] - by_key[(c, model_b)] for c in cases]
    out = {
        "model_a": model_a, "model_b": model_b, "paired_cases": len(diffs),
        "a_wins": sum(d > 0 for d in diffs), "ties": sum(d == 0 for d in diffs),
        "b_wins": sum(d < 0 for d in diffs),
        "mean_difference": round(mean(diffs), 2) if diffs else None,
        "ci_low": None, "ci_high": None, "clear_difference": None,
    }
    if len(diffs) >= min_pairs:
        rng = random.Random(seed)
        n = len(diffs)
        boots = sorted(mean(rng.choices(diffs, k=n)) for _ in range(n_boot))
        out["ci_low"] = round(boots[int(0.025 * n_boot)], 2)
        out["ci_high"] = round(boots[int(0.975 * n_boot) - 1], 2)
        out["clear_difference"] = bool(out["ci_low"] > 0 or out["ci_high"] < 0)
    return out
