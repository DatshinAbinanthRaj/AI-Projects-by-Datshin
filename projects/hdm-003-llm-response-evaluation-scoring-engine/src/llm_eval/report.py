"""Write the results as CSV, JSON and a Markdown report."""
import csv
import json
import os


def _fmt(value, suffix=""):
    return "-" if value is None else f"{value}{suffix}"


def results_rows(rubric, results):
    rows = []
    for r in results:
        auto = r["auto"]
        row = {
            "case_id": r["case_id"], "model": r["model"], "verdict": r["verdict"],
            "score": _fmt(r["score"]), "reasons": "; ".join(r["reasons"]),
            "flags": "; ".join(r["flags"]),
            "fact_coverage": _fmt(None if auto["fact_coverage"] is None else round(auto["fact_coverage"], 2)),
            "missing_facts": "; ".join(auto["missing_facts"]),
            "forbidden_hits": "; ".join(auto["forbidden_hits"]),
            "word_count": auto["word_count"], "evaluators": len(r["evaluators"]),
        }
        for cid in rubric.criterion_ids:
            row[f"mean_{cid}"] = _fmt(r["criterion_means"].get(cid))
        rows.append(row)
    return rows


def to_markdown(rubric, results, summaries, comparison, issues):
    lines = [f"# LLM response evaluation report", "",
             f"Rubric: **{rubric.name}** (scale {rubric.scale_min}-{rubric.scale_max}, "
             f"pass mark {rubric.pass_score:g}/100). Responses scored: {len(results)}.", "",
             "## Model summary", "",
             "| Model | Responses | Pass | Fail | Undecided | Pass rate | Mean score | Flagged for re-review |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for s in summaries:
        rate = "-" if s["pass_rate"] is None else f"{100 * s['pass_rate']:.1f}%"
        lines.append(f"| {s['model']} | {s['responses']} | {s['passed']} | {s['failed']} | "
                     f"{s['undecided']} | {rate} | {_fmt(s['mean_score'])} | {s['flagged_for_review']} |")
    lines += ["", "## Mean rating per criterion", "",
              "| Model | " + " | ".join(rubric.criterion_ids) + " |",
              "|---|" + "---:|" * len(rubric.criterion_ids)]
    for s in summaries:
        lines.append(f"| {s['model']} | " +
                     " | ".join(_fmt(s["criterion_means"][c]) for c in rubric.criterion_ids) + " |")
    lines += ["", "## Failure reasons", "",
              "A response can have more than one reason.", ""]
    all_reasons = sorted({k for s in summaries for k in s["failure_reasons"]})
    if all_reasons:
        lines += ["| Reason | " + " | ".join(s["model"] for s in summaries) + " |",
                  "|---|" + "---:|" * len(summaries)]
        for reason in all_reasons:
            lines.append(f"| {reason} | " +
                         " | ".join(str(s["failure_reasons"].get(reason, 0)) for s in summaries) + " |")
    else:
        lines.append("No failed responses.")
    if comparison:
        c = comparison
        lines += ["", f"## Head to head: {c['model_a']} vs {c['model_b']}", "",
                  f"Cases scored for both models: {c['paired_cases']}. "
                  f"{c['model_a']} better on {c['a_wins']}, tied on {c['ties']}, "
                  f"{c['model_b']} better on {c['b_wins']}.", ""]
        if c["ci_low"] is None:
            lines.append(f"Mean score difference: {_fmt(c['mean_difference'])}. "
                         "Too few shared cases for a bootstrap interval.")
        else:
            verdict = ("The interval does not include 0, so on this data the difference is clear."
                       if c["clear_difference"] else
                       "The interval includes 0, so this data does not clearly separate the models.")
            lines.append(f"Mean score difference ({c['model_a']} minus {c['model_b']}): "
                         f"{c['mean_difference']} points, 95% bootstrap interval "
                         f"{c['ci_low']} to {c['ci_high']}. {verdict}")
    review = [r for r in results if any(f.startswith(("human_auto_mismatch", "evaluator_disagreement"))
                                        for f in r["flags"])]
    lines += ["", "## Responses to re-review", ""]
    if review:
        lines += ["| Case | Model | Verdict | Flags |", "|---|---|---|---|"]
        lines += [f"| {r['case_id']} | {r['model']} | {r['verdict']} | {'; '.join(r['flags'])} |"
                  for r in review]
    else:
        lines.append("None.")
    undecided = [r for r in results if r["verdict"] not in ("PASS", "FAIL")]
    if undecided:
        lines += ["", "## Responses without a verdict", "",
                  "| Case | Model | Status | Missing criteria |", "|---|---|---|---|"]
        lines += [f"| {r['case_id']} | {r['model']} | {r['verdict']} | "
                  f"{', '.join(r['missing_criteria'])} |" for r in undecided]
    lines += ["", "## Input data issues", ""]
    lines += [f"- {i}" for i in issues] if issues else ["None."]
    lines += ["", "_Automated checks are text rules, not proof of correctness. "
              "Scores depend on the human ratings supplied._", ""]
    return "\n".join(lines)


def write_outputs(out_dir, rubric, results, summaries, comparison, issues):
    os.makedirs(out_dir, exist_ok=True)
    rows = results_rows(rubric, results)
    with open(os.path.join(out_dir, "results.csv"), "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump({"rubric": rubric.name, "responses": len(results), "models": summaries,
                   "comparison": comparison, "input_issues": issues}, fh, indent=2)
        fh.write("\n")
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(to_markdown(rubric, results, summaries, comparison, issues))
