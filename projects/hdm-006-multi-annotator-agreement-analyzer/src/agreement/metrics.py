"""Agreement statistics, written with the Python standard library only.

Data shape used everywhere in this module:

    units = {item_id: {annotator_id: label, ...}, ...}

An annotator who did not label an item is simply absent from that item's dict.
Every function returns None when the statistic cannot be calculated (for
example when everybody used a single label, so chance agreement is 100%).
"""
from collections import Counter
from itertools import combinations

LEVELS = ("nominal", "ordinal", "interval")


def percent_agreement(units):
    """Share of annotator pairs, on the same item, that gave the same label."""
    same = total = 0
    for ratings in units.values():
        for a, b in combinations(list(ratings.values()), 2):
            total += 1
            same += a == b
    return same / total if total else None


def cohen_kappa(units, rater_a, rater_b):
    """Cohen's kappa for two annotators, on the items both of them labelled.

    Returns (kappa, raw_agreement, n_items). kappa is None when it is undefined.
    """
    pairs = [(r[rater_a], r[rater_b]) for r in units.values() if rater_a in r and rater_b in r]
    n = len(pairs)
    if n == 0:
        return None, None, 0
    observed = sum(a == b for a, b in pairs) / n
    count_a = Counter(a for a, _ in pairs)
    count_b = Counter(b for _, b in pairs)
    expected = sum(count_a[c] * count_b[c] for c in count_a) / (n * n)
    if expected >= 1:
        return None, observed, n
    return (observed - expected) / (1 - expected), observed, n


def fleiss_kappa(units):
    """Fleiss' kappa. Needs the same number of ratings on every item.

    Items that do not have the most common number of ratings are left out.
    Returns (kappa, items_used, ratings_per_item).
    """
    sizes = Counter(len(r) for r in units.values() if len(r) >= 2)
    if not sizes:
        return None, 0, 0
    m = sizes.most_common(1)[0][0]
    rows = [Counter(r.values()) for r in units.values() if len(r) == m]
    n_items = len(rows)
    totals = Counter()
    p_items = 0.0
    for row in rows:
        totals.update(row)
        p_items += (sum(v * v for v in row.values()) - m) / (m * (m - 1))
    p_bar = p_items / n_items
    p_e = sum((v / (n_items * m)) ** 2 for v in totals.values())
    if p_e >= 1:
        return None, n_items, m
    return (p_bar - p_e) / (1 - p_e), n_items, m


def coincidence_matrix(units):
    """Krippendorff's coincidence matrix as {(label_c, label_k): weight}.

    Each item with m >= 2 ratings adds 1/(m-1) for every ordered pair of
    ratings from two different annotators. Items with one rating add nothing.
    """
    matrix = Counter()
    for ratings in units.values():
        values = list(ratings.values())
        m = len(values)
        if m < 2:
            continue
        for i, c in enumerate(values):
            for j, k in enumerate(values):
                if i != j:
                    matrix[(c, k)] += 1 / (m - 1)
    return matrix


def _distance(level, order, totals):
    """Return a function giving the squared distance between two labels."""
    if level == "nominal":
        return lambda c, k: 0.0 if c == k else 1.0
    if level == "interval":
        return lambda c, k: (float(c) - float(k)) ** 2
    if level == "ordinal":
        position = {label: i for i, label in enumerate(order)}

        def ordinal(c, k):
            if c == k:
                return 0.0
            lo, hi = sorted((position[c], position[k]))
            between = sum(totals.get(order[g], 0) for g in range(lo, hi + 1))
            return (between - (totals.get(c, 0) + totals.get(k, 0)) / 2) ** 2

        return ordinal
    raise ValueError(f"unknown level '{level}'; use one of {', '.join(LEVELS)}")


def krippendorff_alpha(units, level="nominal", order=None):
    """Krippendorff's alpha. Works with missing ratings and any number of annotators.

    level  "nominal" (labels are just names), "ordinal" (labels have an order,
           given by `order`) or "interval" (labels are numbers).
    """
    matrix = coincidence_matrix(units)
    totals = Counter()
    for (c, _), weight in matrix.items():
        totals[c] += weight
    n = sum(totals.values())
    if n <= 1:
        return None
    if level == "ordinal":
        if not order:
            raise ValueError("ordinal level needs the label order")
        missing = [c for c in totals if c not in order]
        if missing:
            raise ValueError(f"labels missing from the order: {sorted(map(str, missing))}")
    delta = _distance(level, order, totals)
    observed = sum(w * delta(c, k) for (c, k), w in matrix.items()) / n
    expected = sum(totals[c] * totals[k] * delta(c, k) for c in totals for k in totals) / (n * (n - 1))
    if expected == 0:
        return None
    return 1 - observed / expected
