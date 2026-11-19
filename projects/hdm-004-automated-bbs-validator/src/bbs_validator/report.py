"""Turn findings into files: findings.csv, summary.json and a self-contained report.html."""
from __future__ import annotations

import csv
import html
import json
import os
from collections import Counter
from dataclasses import dataclass, field

from .rules import ERROR, RULES, WARNING

FINDING_COLUMNS = ["schedule", "line", "bar_mark", "rule", "severity", "message", "suggested_value"]


@dataclass
class ScheduleResult:
    name: str
    verdict: str                 # PASS, REVIEW, FAIL or UNREADABLE
    rows: int = 0
    findings: list = field(default_factory=list)
    weights_kg: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    problem: str = ""            # why the file was unreadable

    def count(self, severity: str) -> int:
        return sum(1 for f in self.findings if f.severity == severity)


def build_summary(results: list, profile_name: str) -> dict:
    by_rule = Counter(f.rule for r in results for f in r.findings)
    verdicts = Counter(r.verdict for r in results)
    return {
        "profile": profile_name,
        "disclaimer": "Automated prototype checks. Not an engineering approval or a code-compliance check.",
        "schedules_checked": len(results),
        "verdicts": {v: verdicts.get(v, 0) for v in ("PASS", "REVIEW", "FAIL", "UNREADABLE")},
        "bar_rows_checked": sum(r.rows for r in results),
        "errors": sum(r.count(ERROR) for r in results),
        "warnings": sum(r.count(WARNING) for r in results),
        "findings_by_rule": {rule: by_rule[rule] for rule in RULES if by_rule[rule]},
        "schedules": [
            {
                "name": r.name,
                "verdict": r.verdict,
                "bar_rows": r.rows,
                "errors": r.count(ERROR),
                "warnings": r.count(WARNING),
                "computed_weight_kg": {str(d): round(w, 1) for d, w in sorted(r.weights_kg.items())},
                "computed_total_weight_kg": round(sum(r.weights_kg.values()), 1),
                "notes": r.notes,
                "problem": r.problem,
            }
            for r in results
        ],
    }


def console_text(results: list) -> str:
    width = max([len(r.name) for r in results] + [8])
    lines = [f"{'Schedule':<{width}}  Verdict     Rows  Errors  Warnings"]
    for r in results:
        lines.append(f"{r.name:<{width}}  {r.verdict:<10}  {r.rows:>4}  {r.count(ERROR):>6}  {r.count(WARNING):>8}")
        if r.problem:
            lines.append(f"{'':<{width}}  {r.problem}")
    return "\n".join(lines)


_CSS = """
body{font-family:Arial,Helvetica,sans-serif;margin:24px;color:#1f2933;max-width:1100px}
h1{font-size:22px}h2{font-size:17px;margin-top:28px}
table{border-collapse:collapse;width:100%;margin:8px 0 16px;font-size:13px}
th,td{border:1px solid #cbd2d9;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#f1f4f7}td.n{text-align:right}
.PASS{background:#d8f3dc}.REVIEW{background:#fff3bf}.FAIL{background:#ffd6d6}.UNREADABLE{background:#e4e7eb}
.error{color:#a61b1b;font-weight:bold}.warning{color:#8a5a00;font-weight:bold}
.note{background:#f1f4f7;border-left:4px solid #7b8794;padding:8px 12px;font-size:13px}
"""


def to_html(results: list, summary: dict) -> str:
    e = html.escape
    parts = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
             "<title>BBS validation report</title><style>", _CSS, "</style></head><body>",
             "<h1>Bar Bending Schedule validation report</h1>",
             f"<p class='note'>{e(summary['disclaimer'])} Rule profile: {e(summary['profile'])}.</p>",
             "<h2>Schedules</h2><table><tr><th>Schedule</th><th>Verdict</th><th>Bar rows</th>"
             "<th>Errors</th><th>Warnings</th><th>Computed weight (kg)</th></tr>"]
    for r in results:
        parts.append(f"<tr><td>{e(r.name)}</td><td class='{r.verdict}'>{r.verdict}</td>"
                     f"<td class='n'>{r.rows}</td><td class='n'>{r.count(ERROR)}</td>"
                     f"<td class='n'>{r.count(WARNING)}</td>"
                     f"<td class='n'>{sum(r.weights_kg.values()):.1f}</td></tr>")
    parts.append("</table>")
    if summary["findings_by_rule"]:
        parts.append("<h2>Findings by rule</h2><table><tr><th>Rule</th><th>Severity</th>"
                     "<th>Meaning</th><th>Count</th></tr>")
        for rule, count in summary["findings_by_rule"].items():
            sev, meaning = RULES[rule]
            parts.append(f"<tr><td>{e(rule)}</td><td class='{sev}'>{sev}</td><td>{e(meaning)}</td>"
                         f"<td class='n'>{count}</td></tr>")
        parts.append("</table>")
    for r in results:
        parts.append(f"<h2>{e(r.name)} &mdash; {r.verdict}</h2>")
        if r.problem:
            parts.append(f"<p class='note'>{e(r.problem)}</p>")
        for note in r.notes:
            parts.append(f"<p class='note'>{e(note)}</p>")
        if not r.findings:
            if not r.problem:
                parts.append("<p>No findings.</p>")
            continue
        parts.append("<table><tr><th>Line</th><th>Bar mark</th><th>Severity</th><th>Rule</th>"
                     "<th>Message</th><th>Suggested value</th></tr>")
        for f in r.findings:
            line = str(f.line) if f.line else "schedule"
            parts.append(f"<tr><td class='n'>{line}</td><td>{e(f.bar_mark)}</td>"
                         f"<td class='{f.severity}'>{f.severity}</td><td>{e(f.rule)}</td>"
                         f"<td>{e(f.message)}</td><td>{e(f.suggested)}</td></tr>")
        parts.append("</table>")
    parts.append("</body></html>")
    return "".join(parts)


def write_outputs(results: list, profile_name: str, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    summary = build_summary(results, profile_name)
    with open(os.path.join(out_dir, "findings.csv"), "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(FINDING_COLUMNS)
        for r in results:
            for f in r.findings:
                writer.writerow([f.schedule, f.line or "", f.bar_mark, f.rule, f.severity,
                                 f.message, f.suggested])
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    with open(os.path.join(out_dir, "report.html"), "w", encoding="utf-8") as handle:
        handle.write(to_html(results, summary))
    return summary
