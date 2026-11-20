"""Write the results as Markdown, JSON and CSV."""
import csv
import json
import os


def fmt(value, digits=3):
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def pct(value):
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def to_markdown(res, source, issues, top_items=15):
    s = res["summary"]
    lines = [f"# Agreement report: {source}", ""]
    lines.append(f"{s['items']} items, {s['annotators']} annotators, {s['ratings']} ratings. "
                 f"Labels treated as **{s['level']}**: {', '.join(s['labels'])}.")
    lines += ["", "## Headline", ""]
    ci = "n/a" if s["alpha_ci_low"] is None else f"{s['alpha_ci_low']:.3f} to {s['alpha_ci_high']:.3f}"
    head = [
        ["Raw agreement (pairs that match)", pct(s["percent_agreement"])],
        [f"Krippendorff's alpha ({s['level']})", fmt(s["krippendorff_alpha"])],
        ["95% bootstrap interval for alpha", ci],
        ["Reading of alpha", s["band"]],
        ["Reading at the low end of the interval", s["band_at_ci_low"]],
        ["Fleiss' kappa", f"{fmt(s['fleiss_kappa'])} (on {s['fleiss_items_used']} items "
                          f"with {s['fleiss_ratings_per_item']} ratings each)"],
    ]
    if s["level"] != "nominal":
        head.insert(2, ["Alpha if the label order is ignored (nominal)", fmt(s["alpha_nominal"])])
    lines.append(_table(["Measure", "Value"], head))
    lines += ["", "Reading: 0.80 and above is usually treated as reliable, 0.667 to 0.80 as usable "
              "with caution, below 0.667 as not reliable. These are conventions, not rules.", ""]

    lines += ["## Annotator pairs (Cohen's kappa)", ""]
    lines.append(_table(
        ["Pair", "Items in common", "Raw agreement", "Kappa", "Enough overlap"],
        [[f"{p['annotator_a']} / {p['annotator_b']}", str(p["items_in_common"]), pct(p["raw_agreement"]),
          fmt(p["cohen_kappa"]), fmt(p["enough_overlap"])] for p in res["pairs"]]))
    lines += ["", "## Annotators", ""]
    lines.append(_table(
        ["Annotator", "Items", "Mean kappa with others", "Alpha without them", "Change if removed"],
        [[a["annotator"], str(a["items_labelled"]), fmt(a["mean_kappa_with_others"]),
          fmt(a["alpha_without_annotator"]),
          "n/a" if a["alpha_change_if_removed"] is None else f"{a['alpha_change_if_removed']:+.3f}"]
         for a in res["annotators"]]))
    lines += ["", "A large positive change means the team agrees better without that person's ratings. "
              "It is a reason to look at their work, not proof that they are wrong.", ""]
    lines += ["## Labels", ""]
    lines.append(_table(
        ["Label", "Times used", "Share", "Alpha (this label vs the rest)"],
        [[str(r["label"]), str(r["times_used"]), pct(r["share_of_ratings"]), fmt(r["alpha_one_vs_rest"])]
         for r in res["labels"]]))
    lines += ["", "## Most confused label pairs", ""]
    lines.append(_table(
        ["Label 1", "Label 2", "Share of all disagreement"],
        [[str(c["label_1"]), str(c["label_2"]), pct(c["share_of_disagreement"])]
         for c in res["confusions"][:8]]) if res["confusions"] else "No disagreement found.")
    split = [r for r in res["items"] if r["distinct_labels"] > 1]
    lines += ["", f"## Items to adjudicate ({len(split)} with any disagreement; most split first)", ""]
    lines.append(_table(
        ["Item", "Ratings", "Distinct labels", "Majority", "Item agreement", "Labels given"],
        [[str(r["item_id"]), str(r["ratings"]), str(r["distinct_labels"]), str(r["majority_label"]) or "tie",
          pct(r["item_agreement"]), r["labels"]] for r in split[:top_items]]) if split else "None.")
    lines += ["", f"## Input problems ({len(issues)})", ""]
    if issues:
        lines.append(_table(["Row", "Problem", "Action"],
                            [[str(i["row"]), i["problem"], i["action"]] for i in issues[:30]]))
        if len(issues) > 30:
            lines.append(f"\n...and {len(issues) - 30} more in issues.csv.")
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def _csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()})


def write_outputs(res, issues, out_dir, source):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as handle:
        handle.write(to_markdown(res, source, issues))
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as handle:
        rounded = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in res["summary"].items()}
        json.dump({"source": source, "summary": rounded, "input_problems": len(issues)}, handle, indent=1)
        handle.write("\n")
    _csv(os.path.join(out_dir, "pairwise.csv"), res["pairs"])
    _csv(os.path.join(out_dir, "annotators.csv"), res["annotators"])
    _csv(os.path.join(out_dir, "labels.csv"), res["labels"])
    _csv(os.path.join(out_dir, "items_to_adjudicate.csv"), [r for r in res["items"] if r["distinct_labels"] > 1])
    _csv(os.path.join(out_dir, "issues.csv"), issues)
