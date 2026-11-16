"""Create a synthetic annotation export with known, deliberately planted problems.

Task being simulated: customer-support tickets labelled with one of four intents.
Nothing here comes from a real company. The planted problems are listed in PROFILES
so the dashboard's findings can be compared with what was put in.
"""
import random

import pandas as pd

LABELS = ["billing", "technical", "account", "other"]
BATCHES = ["B1", "B2", "B3", "B4"]

# accuracy: chance of giving the true label. seconds: typical time per item.
# wrong_to: where this annotator's mistakes go (None = any other label).
PROFILES = {
    "ann_a": {"accuracy": 0.96, "seconds": 36, "wrong_to": None},
    "ann_b": {"accuracy": 0.93, "seconds": 41, "wrong_to": None},
    "ann_c": {"accuracy": 0.91, "seconds": 33, "wrong_to": None},
    # Planted problem 1: mixes up "technical" and "account".
    "ann_d": {"accuracy": 0.70, "seconds": 38, "wrong_to": "swap_technical_account"},
    # Planted problem 2: rushes and falls back on "other".
    "ann_e": {"accuracy": 0.68, "seconds": 9, "wrong_to": "other"},
}
# Planted problem 3: everyone is less accurate in the last batch (guideline drift).
BATCH_PENALTY = {"B4": 0.12}


def _wrong_label(true, rule, rng):
    if rule == "other" and true != "other":
        return "other"
    if rule == "swap_technical_account" and true in ("technical", "account"):
        return "account" if true == "technical" else "technical"
    return rng.choice([x for x in LABELS if x != true])


def generate(n_items=120, per_item=3, gold_per_batch=9, seed=11):
    """Return a DataFrame with one row per (item, annotator) label."""
    rng = random.Random(seed)
    rows = []
    per_batch = n_items // len(BATCHES)
    for i in range(n_items):
        batch = BATCHES[min(i // per_batch, len(BATCHES) - 1)]
        true = rng.choice(LABELS)
        is_gold = (i % per_batch) < gold_per_batch
        for ann in sorted(rng.sample(sorted(PROFILES), per_item)):
            p = PROFILES[ann]
            acc = p["accuracy"] - BATCH_PENALTY.get(batch, 0.0)
            label = true if rng.random() < acc else _wrong_label(true, p["wrong_to"], rng)
            seconds = max(2, round(rng.gauss(p["seconds"], p["seconds"] * 0.25)))
            rows.append({
                "item_id": f"T{i + 1:03d}",
                "annotator_id": ann,
                "label": label,
                "gold_label": true if is_gold else "",
                "batch": batch,
                "seconds_spent": seconds,
            })
    return pd.DataFrame(rows)
