"""Command-line interface: generate, check, queue, decide, report, evaluate."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

from .checks import COLUMNS, check_schedule
from .generate import generate
from .workflow import HUMAN_ROUTES, Store, evaluate, render_report, triage


def read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: str, rows: list[dict], fields: list[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_bbs(path: str) -> list[dict]:
    rows = read_csv(path)
    if not rows:
        raise SystemExit(f"{path}: no data rows")
    absent = [c for c in COLUMNS if c not in rows[0]]
    if absent:
        raise SystemExit(f"{path}: missing columns: {', '.join(absent)}")
    ids = [r["row_id"] for r in rows]
    if not all(i.isdigit() for i in ids) or len(set(ids)) != len(ids):
        raise SystemExit(f"{path}: row_id must be a unique whole number on every row")
    return rows


def load_truth(path: str) -> dict[int, bool]:
    return {int(r["row_id"]): r["is_defect"] == "1" for r in read_csv(path)}


def cmd_generate(a) -> None:
    rows, truth = generate(a.rows, a.seed)
    write_csv(os.path.join(a.out_dir, "sample_bbs.csv"), rows, COLUMNS)
    write_csv(os.path.join(a.out_dir, "sample_truth.csv"), truth,
              ["row_id", "injected_case", "is_defect"])
    print(f"Wrote {len(rows)} synthetic rows and ground truth to {a.out_dir}/")


def cmd_check(a) -> None:
    rows = load_bbs(a.bbs)
    findings = check_schedule(rows)
    routes = triage([int(r["row_id"]) for r in rows], findings, a.sample_rate, a.seed)
    Store(a.db).save_run(rows, findings, routes)
    write_csv(os.path.join(a.out_dir, "findings.csv"),
              [{"row_id": f.row_id, "rule": f.rule, "certain": int(f.certain),
                "message": f.message, "suggested": f.suggested} for f in findings],
              ["row_id", "rule", "certain", "message", "suggested"])
    write_csv(os.path.join(a.out_dir, "routing.csv"),
              [{"row_id": r["row_id"], "bar_mark": r["bar_mark"], "route": routes[int(r["row_id"])]}
               for r in rows], ["row_id", "bar_mark", "route"])
    counts: dict[str, int] = {}
    for route in routes.values():
        counts[route] = counts.get(route, 0) + 1
    print(f"Checked {len(rows)} rows, {len(findings)} findings.")
    for route, n in sorted(counts.items()):
        print(f"  {route:<13} {n}")


def cmd_queue(a) -> None:
    store = Store(a.db)
    queue = store.queue()
    if not queue:
        print("Review queue is empty.")
    for r in queue:
        print(f"Row {r['row_id']} (bar mark {r['bar_mark']}) [{r['route']}]")
        for f in store.findings_for(r["row_id"]):
            print(f"    - {f['rule']}: {f['message']}")
        if r["route"] == "QA_SAMPLE":
            print("    - no automated findings: spot check this row against the drawing")


def cmd_decide(a) -> None:
    try:
        Store(a.db).decide(a.row, a.reviewer, a.decision, a.comment)
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}")
    print(f"Recorded '{a.decision}' for row {a.row} by {a.reviewer}.")


def cmd_import(a) -> None:
    store = Store(a.db)
    n = 0
    for r in read_csv(a.file):
        try:
            store.decide(int(r["row_id"]), r["reviewer"], r["decision"], r.get("comment", ""))
            n += 1
        except ValueError as exc:
            print(f"Skipped row {r.get('row_id')}: {exc}", file=sys.stderr)
    print(f"Imported {n} decisions.")


def cmd_simulate(a) -> None:
    """Write decisions a careful reviewer would make, taken from synthetic ground truth."""
    truth = load_truth(a.truth)
    routes = Store(a.db).routes()
    rows = [{"row_id": rid, "reviewer": "simulated_reviewer",
             "decision": "issue" if truth[rid] else "ok",
             "comment": "simulated from synthetic ground truth"}
            for rid, route in sorted(routes.items()) if route in HUMAN_ROUTES]
    write_csv(a.out, rows, ["row_id", "reviewer", "decision", "comment"])
    print(f"Wrote {len(rows)} simulated decisions to {a.out}")


def cmd_report(a) -> None:
    metrics = Store(a.db).metrics()
    text = render_report(metrics)
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        with open(os.path.splitext(a.out)[0] + ".json", "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, indent=2)
    print(text)


def cmd_evaluate(a) -> None:
    print(json.dumps(evaluate(Store(a.db).routes(), load_truth(a.truth)), indent=2))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="rebar_qa", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("generate", help="create a synthetic BBS with injected defects")
    s.add_argument("--rows", type=int, default=60)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--out-dir", default="data")
    s.set_defaults(func=cmd_generate)

    s = sub.add_parser("check", help="run checks and route every row")
    s.add_argument("bbs")
    s.add_argument("--db", default="qa.db")
    s.add_argument("--sample-rate", type=float, default=0.1)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--out-dir", default="out")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("queue", help="list rows waiting for a human")
    s.add_argument("--db", default="qa.db")
    s.set_defaults(func=cmd_queue)

    s = sub.add_parser("decide", help="record one human decision")
    s.add_argument("--db", default="qa.db")
    s.add_argument("--row", type=int, required=True)
    s.add_argument("--reviewer", required=True)
    s.add_argument("--decision", choices=["issue", "ok"], required=True)
    s.add_argument("--comment", default="")
    s.set_defaults(func=cmd_decide)

    s = sub.add_parser("import-decisions", help="record decisions from a CSV file")
    s.add_argument("file")
    s.add_argument("--db", default="qa.db")
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("simulate-review", help="write simulated decisions from ground truth")
    s.add_argument("--db", default="qa.db")
    s.add_argument("--truth", required=True)
    s.add_argument("--out", default="out/decisions.csv")
    s.set_defaults(func=cmd_simulate)

    s = sub.add_parser("report", help="print metrics; optionally save markdown and JSON")
    s.add_argument("--db", default="qa.db")
    s.add_argument("--out", default="")
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("evaluate", help="compare routing with synthetic ground truth")
    s.add_argument("--db", default="qa.db")
    s.add_argument("--truth", required=True)
    s.set_defaults(func=cmd_evaluate)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
