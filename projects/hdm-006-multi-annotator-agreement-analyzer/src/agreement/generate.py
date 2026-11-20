"""Synthetic sample data. Nothing here comes from a real project.

Three files are produced, each built to show one thing:

moderation_long.csv   Nominal labels, long layout, 5 annotators, 3 per item.
                      Planted: `spam` and `misinformation` items are hard to tell
                      apart for everyone, and ann_5 is careless.
quality_wide.csv      Ordinal 1-5 quality ratings, wide layout, 4 raters, some
                      empty cells. Planted: rater_d scores one point higher.
skewed_two_raters.csv Two raters, 95% of items `safe`. High raw agreement,
                      low kappa (the "prevalence" effect).
"""
import csv
import random

MODERATION_LABELS = ["safe", "spam", "harassment", "misinformation"]
QUALITY_ORDER = ["1", "2", "3", "4", "5"]


def moderation(seed=21, n_items=150):
    rng = random.Random(seed)
    accuracy = {"ann_1": 0.95, "ann_2": 0.93, "ann_3": 0.92, "ann_4": 0.90, "ann_5": 0.70}
    rows, truth = [], []
    for i in range(1, n_items + 1):
        item = f"post_{i:03d}"
        true = rng.choices(MODERATION_LABELS, weights=[50, 20, 15, 15])[0]
        truth.append({"item_id": item, "true_label": true})
        for ann in sorted(rng.sample(sorted(accuracy), 3)):
            if true in ("spam", "misinformation") and rng.random() < 0.30:
                label = "misinformation" if true == "spam" else "spam"   # planted ambiguity
            elif rng.random() < accuracy[ann]:
                label = true
            else:
                label = rng.choice([x for x in MODERATION_LABELS if x != true])
            rows.append({"item_id": item, "annotator_id": ann, "label": label})
    return rows, truth


def quality(seed=22, n_items=80):
    rng = random.Random(seed)
    raters = ["rater_a", "rater_b", "rater_c", "rater_d"]
    rows = []
    for i in range(1, n_items + 1):
        true = rng.choices([1, 2, 3, 4, 5], weights=[10, 20, 30, 25, 15])[0]
        row = {"item_id": f"resp_{i:03d}"}
        for r in raters:
            if rng.random() < 0.10:
                row[r] = ""                       # rater did not see this item
                continue
            score = true + rng.choices([-1, 0, 1], weights=[15, 70, 15])[0]
            if r == "rater_d":
                score += 1                        # planted: lenient rater
            row[r] = str(min(5, max(1, score)))
        rows.append(row)
    return rows, ["item_id"] + raters


def skewed(seed=23, n_items=100):
    rng = random.Random(seed)
    rows = []
    for i in range(1, n_items + 1):
        true = "unsafe" if i % 20 == 0 else "safe"     # 5% unsafe
        row = {"item_id": f"msg_{i:03d}"}
        for r in ("rater_x", "rater_y"):
            wrong = rng.random() < 0.04
            row[r] = ("safe" if true == "unsafe" else "unsafe") if wrong else true
        rows.append(row)
    return rows, ["item_id", "rater_x", "rater_y"]


def _write(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_all(data_dir):
    rows, truth = moderation()
    _write(f"{data_dir}/moderation_long.csv", rows, ["item_id", "annotator_id", "label"])
    _write(f"{data_dir}/moderation_truth.csv", truth, ["item_id", "true_label"])
    rows, fields = quality()
    _write(f"{data_dir}/quality_wide.csv", rows, fields)
    rows, fields = skewed()
    _write(f"{data_dir}/skewed_two_raters.csv", rows, fields)
