"""Turn an analysis result into a Markdown report and output files."""
import json
import os
from dataclasses import asdict


def pct(x):
    return "n/a" if x is None or x != x else f"{x * 100:.1f}%"


def _md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def to_markdown(res, source="annotations"):
    s, th = res["summary"], res["thresholds"]
    lines = [f"# Annotation quality report: {source}", "",
             f"- Rows received: {s['rows_received']}, used: {s['rows_used']}, validation issues: {s['validation_issues']}",
             f"- Items: {s['items']} ({s['gold_items']} gold), annotators: {s['annotators']}",
             f"- Gold accuracy (all annotators): {pct(s['gold_accuracy'])}",
             f"- Pairwise agreement: {pct(s['agreement_rate'])}",
             f"- Disputed items: {s['disputed_items']} ({pct(s['disputed_share'])} of items with 2+ labels)",
             f"- Flagged annotators: {', '.join(s['flagged_annotators']) or 'none'}", "",
             "## Annotators", ""]
    rows = []
    for r in res["annotators"].to_dict("records"):
        ci = "n/a" if r["gold_items"] == 0 else f"{pct(r['accuracy_ci_low'])} to {pct(r['accuracy_ci_high'])}"
        speed = "n/a" if r["speed_ratio"] is None else f"{r['speed_ratio']:.2f}"
        rows.append([r["annotator_id"], r["labels"], f"{r['gold_correct']}/{r['gold_items']}",
                     pct(r["gold_accuracy"]), ci, pct(r["agreement_rate"]), speed,
                     f"{r['label_bias'] * 100:.0f} pts ({r['bias_label']})", r["flags"] or "-", r["accuracy_evidence"] or "-"])
    lines.append(_md_table(["Annotator", "Labels", "Gold correct", "Gold accuracy", "95% interval",
                            "Agreement", "Speed ratio", "Label bias", "Flags", "Accuracy evidence"], rows))
    lines += ["", "Accuracy evidence is `strong` only when the whole 95% interval is below the threshold; "
              "`weak` means the gold sample is too small to be sure."]
    lines += ["", "## Batches", "",
              _md_table(["Batch", "Labels", "Gold accuracy", "Agreement"],
                        [[r["batch"], r["labels"], pct(r["gold_accuracy"]), pct(r["agreement_rate"])]
                         for r in res["batches"].to_dict("records")])]
    conf = res["confusion"]
    if not conf.empty:
        lines += ["", "## Confusion on gold items (rows = correct label, columns = label given)", "",
                  _md_table(["gold \\ given"] + list(conf.columns),
                            [[idx] + list(row) for idx, row in zip(conf.index, conf.values.tolist())])]
    lines += ["", "## Thresholds used", ""] + [f"- {k}: {v}" for k, v in asdict(th).items()]
    lines += ["", "A flag is a reason to look closer, not a verdict about a person."]
    return "\n".join(lines) + "\n"


def write_outputs(res, out_dir, source="annotations"):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(res, source))
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": res["summary"], "thresholds": asdict(res["thresholds"])}, f, indent=2)
    res["annotators"].round(4).to_csv(os.path.join(out_dir, "annotators.csv"), index=False)
    items = res["items"]
    items[items["disputed"]].drop(columns="disputed").to_csv(
        os.path.join(out_dir, "disputed_items.csv"), index=False)
    res["issues"].to_csv(os.path.join(out_dir, "validation_issues.csv"), index=False)
