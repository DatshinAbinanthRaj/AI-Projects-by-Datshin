"""Quality-control metrics for an annotation export.

Input: one row per label given by one annotator to one item.
Columns: item_id, annotator_id, label, gold_label, batch, seconds_spent.
gold_label is filled only for "gold" items, where the correct answer is known.
"""
from dataclasses import dataclass
from itertools import combinations
from math import sqrt

import pandas as pd

REQUIRED = ["item_id", "annotator_id", "label", "gold_label", "batch", "seconds_spent"]


@dataclass
class Thresholds:
    min_accuracy: float = 0.80     # gold accuracy below this is flagged
    min_gold: int = 10             # gold items needed before accuracy is judged
    min_agreement: float = 0.70    # agreement with peers below this is flagged
    min_pairs: int = 20            # comparisons needed before agreement is judged
    min_speed_ratio: float = 0.40  # median time below 40% of the team median is flagged
    max_label_bias: float = 0.20   # label share this far from the team's share is flagged


def wilson_interval(successes, n, z=1.96):
    """95% Wilson score interval for a proportion. Honest about small samples."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def validate(df, allowed_labels=None):
    """Clean the export. Returns (clean_df, issues).

    Rows that cannot be used are dropped and listed in `issues`, so nothing
    disappears silently. A missing column stops the run with ValueError.
    """
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}")
    df = df[REQUIRED].copy()
    for col in ["item_id", "annotator_id", "label", "gold_label", "batch"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    issues = []

    def drop(mask, text):
        nonlocal df
        for idx in df.index[mask]:
            issues.append({"row": int(idx) + 2, "item_id": df.at[idx, "item_id"],
                           "annotator_id": df.at[idx, "annotator_id"],
                           "issue": text, "action": "row dropped"})
        df = df[~mask]

    drop((df["item_id"] == "") | (df["annotator_id"] == "") | (df["label"] == ""),
         "blank item_id, annotator_id or label")
    if allowed_labels:
        drop(~df["label"].isin(allowed_labels), "label is not in the allowed label set")
    drop(df.duplicated(["item_id", "annotator_id"], keep="first"),
         "same annotator labelled the same item twice")

    secs = pd.to_numeric(df["seconds_spent"], errors="coerce")
    bad = secs.isna() | (secs <= 0)
    for idx in df.index[bad]:
        issues.append({"row": int(idx) + 2, "item_id": df.at[idx, "item_id"],
                       "annotator_id": df.at[idx, "annotator_id"],
                       "issue": "seconds_spent is missing or not a positive number",
                       "action": "time ignored, label kept"})
    df["seconds_spent"] = secs.where(~bad)

    golds = df[df["gold_label"] != ""].groupby("item_id")["gold_label"].nunique()
    for item in golds[golds > 1].index:
        issues.append({"row": None, "item_id": item, "annotator_id": "",
                       "issue": "item has more than one gold label",
                       "action": "gold ignored for this item"})
        df.loc[df["item_id"] == item, "gold_label"] = ""
    # A gold label given on one row applies to every row of that item.
    gold_map = df[df["gold_label"] != ""].groupby("item_id")["gold_label"].first()
    df["gold_label"] = df["item_id"].map(gold_map).fillna("")
    return df.reset_index(drop=True), issues


def pairwise(df):
    """One row per pair of annotators who labelled the same item."""
    rows = []
    for item, g in df.groupby("item_id", sort=True):
        recs = g[["annotator_id", "label", "batch"]].to_dict("records")
        for a, b in combinations(recs, 2):
            rows.append({"item_id": item, "batch": a["batch"],
                         "annotator_a": a["annotator_id"], "annotator_b": b["annotator_id"],
                         "agree": a["label"] == b["label"]})
    return pd.DataFrame(rows, columns=["item_id", "batch", "annotator_a", "annotator_b", "agree"])


def annotator_metrics(df, th=None):
    """One row per annotator with accuracy, agreement, speed, bias and flags."""
    th = th or Thresholds()
    pairs = pairwise(df)
    team_median = df["seconds_spent"].median()
    rows = []
    for ann, g in df.groupby("annotator_id", sort=True):
        gold = g[g["gold_label"] != ""]
        n_gold = len(gold)
        correct = int((gold["label"] == gold["gold_label"]).sum())
        acc = correct / n_gold if n_gold else None
        low, high = wilson_interval(correct, n_gold)
        mine = pairs[(pairs["annotator_a"] == ann) | (pairs["annotator_b"] == ann)]
        n_pairs = len(mine)
        agreement = float(mine["agree"].mean()) if n_pairs else None
        median_s = g["seconds_spent"].median()
        speed = float(median_s / team_median) if pd.notna(median_s) and team_median else None
        # Bias: compare this annotator's label mix with everyone else's.
        others = df[df["annotator_id"] != ann]["label"].value_counts(normalize=True)
        own = g["label"].value_counts(normalize=True)
        diff = own.subtract(others, fill_value=0.0)
        bias = float(diff.abs().max()) if len(others) else 0.0
        bias_label = diff.abs().idxmax() if len(others) else ""

        flags = []
        evidence = ""
        if n_gold >= th.min_gold and acc < th.min_accuracy:
            flags.append("LOW_GOLD_ACCURACY")
            # Strong only if even the top of the interval is below the threshold.
            evidence = "strong" if high < th.min_accuracy else "weak"
        if n_pairs >= th.min_pairs and agreement < th.min_agreement:
            flags.append("LOW_AGREEMENT")
        if speed is not None and speed < th.min_speed_ratio:
            flags.append("TOO_FAST")
        if bias > th.max_label_bias:
            flags.append("LABEL_BIAS")
        notes = []
        if n_gold < th.min_gold:
            notes.append(f"only {n_gold} gold items: accuracy not judged")
        if n_pairs < th.min_pairs:
            notes.append(f"only {n_pairs} comparisons: agreement not judged")
        rows.append({
            "annotator_id": ann, "labels": len(g), "gold_items": n_gold,
            "gold_correct": correct, "gold_accuracy": acc,
            "accuracy_ci_low": low if n_gold else None,
            "accuracy_ci_high": high if n_gold else None,
            "accuracy_evidence": evidence,
            "comparisons": n_pairs, "agreement_rate": agreement,
            "median_seconds": float(median_s) if pd.notna(median_s) else None,
            "speed_ratio": speed, "label_bias": bias, "bias_label": bias_label,
            "flags": ", ".join(flags), "notes": "; ".join(notes),
        })
    return pd.DataFrame(rows)


def item_table(df):
    """One row per item: how many labels it got and whether they agree."""
    rows = []
    for item, g in df.groupby("item_id", sort=True):
        counts = g["label"].value_counts()
        top = counts[counts == counts.max()].index.tolist()
        rows.append({
            "item_id": item, "batch": g["batch"].iloc[0], "annotators": len(g),
            "labels_given": " | ".join(f"{a}={l}" for a, l in zip(g["annotator_id"], g["label"])),
            "majority_label": top[0] if len(top) == 1 else "",  # empty = tie
            "gold_label": g["gold_label"].iloc[0],
            "disputed": len(counts) > 1,
        })
    return pd.DataFrame(rows)


def batch_metrics(df):
    """Gold accuracy and agreement per batch, to spot quality drifting over time."""
    pairs = pairwise(df)
    rows = []
    for batch, g in df.groupby("batch", sort=True):
        gold = g[g["gold_label"] != ""]
        p = pairs[pairs["batch"] == batch]
        rows.append({
            "batch": batch, "labels": len(g), "gold_labels": len(gold),
            "gold_accuracy": float((gold["label"] == gold["gold_label"]).mean()) if len(gold) else None,
            "agreement_rate": float(p["agree"].mean()) if len(p) else None,
        })
    return pd.DataFrame(rows)


def confusion(df):
    """Rows = gold label, columns = label given. Shows which classes get mixed up."""
    gold = df[df["gold_label"] != ""]
    if gold.empty:
        return pd.DataFrame()
    labels = sorted(set(gold["gold_label"]) | set(gold["label"]))
    table = pd.crosstab(gold["gold_label"], gold["label"])
    return table.reindex(index=labels, columns=labels, fill_value=0)


def analyse(raw, th=None, allowed_labels=None):
    """Run everything. Returns a dict of tables plus a small summary."""
    th = th or Thresholds()
    df, issues = validate(raw, allowed_labels)
    annot = annotator_metrics(df, th)
    items = item_table(df)
    pairs = pairwise(df)
    gold = df[df["gold_label"] != ""]
    multi = items[items["annotators"] > 1]
    summary = {
        "rows_received": int(len(raw)), "rows_used": int(len(df)),
        "validation_issues": len(issues),
        "items": int(df["item_id"].nunique()), "annotators": int(df["annotator_id"].nunique()),
        "gold_items": int(gold["item_id"].nunique()),
        "gold_accuracy": float((gold["label"] == gold["gold_label"]).mean()) if len(gold) else None,
        "agreement_rate": float(pairs["agree"].mean()) if len(pairs) else None,
        "disputed_items": int(multi["disputed"].sum()),
        "disputed_share": float(multi["disputed"].mean()) if len(multi) else None,
        "flagged_annotators": annot.loc[annot["flags"] != "", "annotator_id"].tolist() if len(annot) else [],
    }
    issue_table = pd.DataFrame(issues, columns=["row", "item_id", "annotator_id", "issue", "action"])
    issue_table["row"] = issue_table["row"].astype("Int64")  # whole numbers, blank when not row-specific
    return {"clean": df, "issues": issue_table,
            "annotators": annot, "items": items, "batches": batch_metrics(df),
            "confusion": confusion(df), "summary": summary, "thresholds": th}
