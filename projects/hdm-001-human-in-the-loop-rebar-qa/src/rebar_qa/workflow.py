"""Triage, review queue, audit trail and metrics for the HITL workflow."""
from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timezone

from .checks import Finding

AUTO_ACCEPT = "AUTO_ACCEPT"     # no findings, not sampled
AUTO_FLAG = "AUTO_FLAG"         # only certain errors: return to detailer
HUMAN_REVIEW = "HUMAN_REVIEW"   # at least one finding needs judgement
QA_SAMPLE = "QA_SAMPLE"         # clean row picked for a human spot check
HUMAN_ROUTES = (HUMAN_REVIEW, QA_SAMPLE)
DECISIONS = ("issue", "ok")


def triage(row_ids: list[int], findings: list[Finding],
           sample_rate: float = 0.1, seed: int = 0) -> dict[int, str]:
    """Decide where each row goes. Clean rows are randomly sampled for QA."""
    if not 0 <= sample_rate <= 1:
        raise ValueError("sample_rate must be between 0 and 1")
    by_row: dict[int, list[Finding]] = {}
    for f in findings:
        by_row.setdefault(f.row_id, []).append(f)
    routes: dict[int, str] = {}
    clean: list[int] = []
    for rid in row_ids:
        fs = by_row.get(rid, [])
        if not fs:
            clean.append(rid)
            routes[rid] = AUTO_ACCEPT
        elif any(not f.certain for f in fs):
            routes[rid] = HUMAN_REVIEW
        else:
            routes[rid] = AUTO_FLAG
    if clean and sample_rate > 0:
        k = max(1, round(len(clean) * sample_rate))
        for rid in random.Random(seed).sample(clean, k):
            routes[rid] = QA_SAMPLE
    return routes


class Store:
    """SQLite store: one QA run plus an append-only log of human decisions."""

    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS rows(row_id INTEGER PRIMARY KEY, bar_mark TEXT, route TEXT);
            CREATE TABLE IF NOT EXISTS findings(row_id INTEGER, rule TEXT, certain INTEGER,
                                                message TEXT, suggested TEXT);
            CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY AUTOINCREMENT,
                row_id INTEGER, reviewer TEXT, decision TEXT, comment TEXT, decided_at TEXT);
        """)

    def save_run(self, rows: list[dict], findings: list[Finding], routes: dict[int, str]) -> None:
        with self.db:
            for table in ("rows", "findings", "decisions"):
                self.db.execute(f"DELETE FROM {table}")
            self.db.executemany("INSERT INTO rows VALUES (?,?,?)",
                                [(int(r["row_id"]), r.get("bar_mark", ""), routes[int(r["row_id"])])
                                 for r in rows])
            self.db.executemany("INSERT INTO findings VALUES (?,?,?,?,?)",
                                [(f.row_id, f.rule, int(f.certain), f.message, f.suggested)
                                 for f in findings])

    def route_of(self, row_id: int):
        r = self.db.execute("SELECT route FROM rows WHERE row_id=?", (row_id,)).fetchone()
        return r["route"] if r else None

    def routes(self) -> dict[int, str]:
        return {r["row_id"]: r["route"] for r in self.db.execute("SELECT row_id, route FROM rows")}

    def findings_for(self, row_id: int) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM findings WHERE row_id=?", (row_id,)).fetchall()

    def latest_decisions(self) -> dict[int, sqlite3.Row]:
        """Latest decision per row. Earlier ones stay in the table as audit trail."""
        return {r["row_id"]: r for r in self.db.execute("SELECT * FROM decisions ORDER BY id")}

    def queue(self) -> list[sqlite3.Row]:
        """Rows waiting for a human decision."""
        done = set(self.latest_decisions())
        rows = self.db.execute(
            "SELECT * FROM rows WHERE route IN (?,?) ORDER BY row_id", HUMAN_ROUTES).fetchall()
        return [r for r in rows if r["row_id"] not in done]

    def decide(self, row_id: int, reviewer: str, decision: str, comment: str = "") -> None:
        route = self.route_of(row_id)
        if route is None:
            raise ValueError(f"Row {row_id} is not in this run")
        if route not in HUMAN_ROUTES:
            raise ValueError(f"Row {row_id} was routed to {route}; it is not in the review queue")
        if decision not in DECISIONS:
            raise ValueError(f"Decision must be one of {DECISIONS}")
        if not reviewer.strip():
            raise ValueError("Reviewer name is required for the audit trail")
        with self.db:
            self.db.execute(
                "INSERT INTO decisions(row_id, reviewer, decision, comment, decided_at) VALUES (?,?,?,?,?)",
                (row_id, reviewer.strip(), decision, comment,
                 datetime.now(timezone.utc).isoformat(timespec="seconds")))

    def metrics(self) -> dict:
        routes = self.routes()
        total = len(routes)
        counts = {k: 0 for k in (AUTO_ACCEPT, AUTO_FLAG, HUMAN_REVIEW, QA_SAMPLE)}
        for route in routes.values():
            counts[route] += 1
        latest = self.latest_decisions()

        def split(route: str) -> tuple[int, int]:
            dec = [d["decision"] for rid, d in latest.items() if routes.get(rid) == route]
            return dec.count("issue"), dec.count("ok")

        hr_issue, hr_ok = split(HUMAN_REVIEW)
        qa_issue, qa_ok = split(QA_SAMPLE)
        rules: dict[str, dict] = {}
        for f in self.db.execute("SELECT row_id, rule, certain FROM findings"):
            s = rules.setdefault(f["rule"], {"findings": 0, "certain": bool(f["certain"]),
                                             "confirmed": 0, "false_alarm": 0})
            s["findings"] += 1
            d = latest.get(f["row_id"])
            if d is not None and not f["certain"]:
                s["confirmed" if d["decision"] == "issue" else "false_alarm"] += 1
        ratio = lambda n, d: round(n / d, 3) if d else None
        return {
            "total_rows": total,
            "routes": counts,
            "automation_rate": ratio(counts[AUTO_ACCEPT] + counts[AUTO_FLAG], total),
            "pending_reviews": len(self.queue()),
            "human_review": {"decided": hr_issue + hr_ok, "confirmed_issue": hr_issue,
                             "false_alarm": hr_ok,
                             "false_alarm_rate": ratio(hr_ok, hr_issue + hr_ok)},
            "qa_sample": {"decided": qa_issue + qa_ok, "escaped_defects": qa_issue,
                          "escape_rate": ratio(qa_issue, qa_issue + qa_ok)},
            "rules": dict(sorted(rules.items())),
        }


def evaluate(routes: dict[int, str], truth: dict[int, bool]) -> dict:
    """Compare routing with known (synthetic) ground truth: is_defect per row."""
    defects = [rid for rid, bad in truth.items() if bad]
    clean = [rid for rid, bad in truth.items() if not bad]
    caught = [rid for rid in defects if routes[rid] in (AUTO_FLAG, HUMAN_REVIEW)]
    missed = sorted(set(defects) - set(caught))
    return {
        "defect_rows": len(defects),
        "defects_caught": len(caught),
        "defects_missed": missed,
        "recall": round(len(caught) / len(defects), 3) if defects else None,
        "clean_rows": len(clean),
        "clean_rows_auto_flagged": sum(routes[r] == AUTO_FLAG for r in clean),
        "clean_rows_sent_to_human_review": sum(routes[r] == HUMAN_REVIEW for r in clean),
    }


def render_report(m: dict) -> str:
    pct = lambda x: "n/a" if x is None else f"{x * 100:.1f} %"
    r = m["routes"]
    lines = [
        "# Rebar QA run report", "",
        "Synthetic demonstration data. Prototype output: requires engineering review.", "",
        "## Routing", "",
        "| Route | Rows |", "|---|---:|",
        f"| Auto-accepted | {r[AUTO_ACCEPT]} |",
        f"| Auto-flagged (returned to detailer) | {r[AUTO_FLAG]} |",
        f"| Human review | {r[HUMAN_REVIEW]} |",
        f"| QA sample of clean rows | {r[QA_SAMPLE]} |",
        f"| **Total** | **{m['total_rows']}** |", "",
        f"- Automation rate (rows needing no human): {pct(m['automation_rate'])}",
        f"- Reviews still pending: {m['pending_reviews']}", "",
        "## Human review outcomes", "",
        f"- Human-review rows decided: {m['human_review']['decided']} "
        f"({m['human_review']['confirmed_issue']} confirmed issues, "
        f"{m['human_review']['false_alarm']} false alarms, "
        f"false-alarm rate {pct(m['human_review']['false_alarm_rate'])})",
        f"- QA-sampled clean rows decided: {m['qa_sample']['decided']} "
        f"({m['qa_sample']['escaped_defects']} escaped defects, "
        f"escape rate {pct(m['qa_sample']['escape_rate'])})", "",
        "## Findings by rule", "",
        "| Rule | Type | Findings | Confirmed by human | False alarm |", "|---|---|---:|---:|---:|",
    ]
    for name, s in m["rules"].items():
        kind = "certain" if s["certain"] else "needs judgement"
        conf = "-" if s["certain"] else s["confirmed"]
        fa = "-" if s["certain"] else s["false_alarm"]
        lines.append(f"| {name} | {kind} | {s['findings']} | {conf} | {fa} |")
    return "\n".join(lines) + "\n"
