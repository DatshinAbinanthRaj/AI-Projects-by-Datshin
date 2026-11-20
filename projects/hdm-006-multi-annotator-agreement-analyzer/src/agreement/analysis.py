"""Turn a set of ratings into the tables a data operations lead needs."""
import random
from collections import Counter
from itertools import combinations

from . import metrics

# Krippendorff's commonly quoted cut-offs. They are conventions, not laws:
# the right bar depends on what the labels are used for.
RELIABLE = 0.80
TENTATIVE = 0.667


def band(alpha):
    if alpha is None:
        return "undefined"
    if alpha >= RELIABLE:
        return "reliable"
    if alpha >= TENTATIVE:
        return "tentative"
    return "unreliable"


def annotators(units):
    return sorted({a for ratings in units.values() for a in ratings})


def labels_used(units):
    return sorted({v for ratings in units.values() for v in ratings.values()}, key=str)


def bootstrap_alpha(units, level, order, reps=1000, seed=7, confidence=0.95):
    """Percentile bootstrap interval for alpha, resampling items with replacement."""
    ids = list(units)
    if len(ids) < 2 or reps <= 0:
        return None, None
    rng = random.Random(seed)
    values = []
    for _ in range(reps):
        sample = {i: units[rng.choice(ids)] for i in range(len(ids))}
        a = metrics.krippendorff_alpha(sample, level, order)
        if a is not None:
            values.append(a)
    if len(values) < reps * 0.9:
        return None, None
    values.sort()
    tail = (1 - confidence) / 2
    return values[int(tail * len(values))], values[min(len(values) - 1, int((1 - tail) * len(values)))]


def pairwise_table(units, min_overlap=10):
    rows = []
    for a, b in combinations(annotators(units), 2):
        kappa, raw, n = metrics.cohen_kappa(units, a, b)
        rows.append({
            "annotator_a": a, "annotator_b": b, "items_in_common": n,
            "raw_agreement": raw, "cohen_kappa": kappa,
            "enough_overlap": n >= min_overlap,
        })
    return rows


def annotator_table(units, level, order, overall_alpha, pairs, min_overlap=10):
    """Per annotator: average kappa with the others, and alpha with them removed."""
    rows = []
    for a in annotators(units):
        kappas = [p["cohen_kappa"] for p in pairs
                  if a in (p["annotator_a"], p["annotator_b"])
                  and p["cohen_kappa"] is not None and p["items_in_common"] >= min_overlap]
        without = {i: {k: v for k, v in r.items() if k != a} for i, r in units.items()}
        alpha_without = metrics.krippendorff_alpha(without, level, order)
        change = None
        if alpha_without is not None and overall_alpha is not None:
            change = alpha_without - overall_alpha
        rows.append({
            "annotator": a,
            "items_labelled": sum(a in r for r in units.values()),
            "mean_kappa_with_others": sum(kappas) / len(kappas) if kappas else None,
            "alpha_without_annotator": alpha_without,
            "alpha_change_if_removed": change,
        })
    return rows


def label_table(units):
    """Per label: alpha after collapsing the task to 'this label or anything else'."""
    counts = Counter(v for r in units.values() for v in r.values())
    rows = []
    for label in labels_used(units):
        collapsed = {i: {a: (v == label) for a, v in r.items()} for i, r in units.items()}
        rows.append({
            "label": label, "times_used": counts[label],
            "share_of_ratings": counts[label] / sum(counts.values()),
            "alpha_one_vs_rest": metrics.krippendorff_alpha(collapsed, "nominal"),
        })
    return rows


def confusion_pairs(units):
    """Which two labels are most often given to the same item by different people."""
    matrix = metrics.coincidence_matrix(units)
    off = Counter()
    for (c, k), w in matrix.items():
        if c != k:
            off[tuple(sorted((c, k), key=str))] += w / 2
    total = sum(off.values())
    return [{"label_1": c, "label_2": k, "weight": w, "share_of_disagreement": w / total}
            for (c, k), w in sorted(off.items(), key=lambda x: (-x[1], str(x[0])))]


def item_table(units):
    """Per item: how split the annotators were. Used to pick items for adjudication."""
    rows = []
    for item, ratings in units.items():
        if len(ratings) < 2:
            continue
        counts = Counter(ratings.values())
        top, top_n = sorted(counts.items(), key=lambda x: (-x[1], str(x[0])))[0]
        pairs = len(ratings) * (len(ratings) - 1) / 2
        agree = sum(v * (v - 1) / 2 for v in counts.values()) / pairs
        rows.append({
            "item_id": item, "ratings": len(ratings), "distinct_labels": len(counts),
            "majority_label": top if list(counts.values()).count(top_n) == 1 else "",
            "item_agreement": agree,
            "labels": "; ".join(f"{a}={v}" for a, v in sorted(ratings.items())),
        })
    rows.sort(key=lambda r: (r["item_agreement"], -r["distinct_labels"], str(r["item_id"])))
    return rows


def analyse(units, level="nominal", order=None, reps=1000, seed=7, min_overlap=10):
    """Run every calculation and return one dictionary with all results."""
    rated = {i: r for i, r in units.items() if len(r) >= 2}
    if not rated:
        raise ValueError("no item has ratings from two or more annotators")
    if level == "interval":
        try:
            units = {i: {a: float(v) for a, v in r.items()} for i, r in units.items()}
        except ValueError as err:
            raise ValueError(f"interval level needs numeric labels ({err})") from None
    if level == "ordinal" and not order:
        raise ValueError("ordinal level needs --order, the labels from lowest to highest")
    alpha = metrics.krippendorff_alpha(units, level, order)
    low, high = bootstrap_alpha(rated, level, order, reps, seed)
    fleiss, fleiss_items, fleiss_m = metrics.fleiss_kappa(units)
    pairs = pairwise_table(units, min_overlap)
    items = item_table(units)
    summary = {
        "level": level,
        "items": len(units),
        "items_with_two_or_more_ratings": len(rated),
        "annotators": len(annotators(units)),
        "ratings": sum(len(r) for r in units.values()),
        "labels": [str(x) for x in (order or labels_used(units))],
        "percent_agreement": metrics.percent_agreement(units),
        "krippendorff_alpha": alpha,
        "alpha_nominal": alpha if level == "nominal" else metrics.krippendorff_alpha(
            {i: {a: str(v) for a, v in r.items()} for i, r in units.items()}, "nominal"),
        "alpha_ci_low": low, "alpha_ci_high": high, "bootstrap_reps": reps, "seed": seed,
        "band": band(alpha),
        # The cautious reading: judge by the low end of the interval when there is one.
        "band_at_ci_low": band(low) if low is not None else band(alpha),
        "fleiss_kappa": fleiss, "fleiss_items_used": fleiss_items, "fleiss_ratings_per_item": fleiss_m,
        "items_with_any_disagreement": sum(r["distinct_labels"] > 1 for r in items),
    }
    return {
        "summary": summary,
        "pairs": pairs,
        "annotators": annotator_table(units, level, order, alpha, pairs, min_overlap),
        "labels": label_table(units),
        "confusions": confusion_pairs(units),
        "items": items,
    }
