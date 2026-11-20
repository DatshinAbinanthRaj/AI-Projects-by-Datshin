"""Command line entry point.

    python run.py generate
    python run.py report --out-dir out
    python run.py report --tasks T.csv --workforce W.csv --targets K.json --out-dir out

Exit code: 0 no KPI is off target in the latest week, 1 at least one is, 2 the input could not be used.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

import pandas as pd  # noqa: E402

from ops_kpi import generate as gen  # noqa: E402
from ops_kpi.dashboard import STATUS_WORD, build, fmt  # noqa: E402
from ops_kpi.kpis import analyse  # noqa: E402
from ops_kpi.loaders import load_targets, load_tasks, load_workforce  # noqa: E402


def write_outputs(res, targets, issues, out_dir, source, synthetic=False):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "dashboard.html"), "w", encoding="utf-8") as handle:
        handle.write(build(res, targets, issues, source, synthetic))
    weekly = res["weekly"].copy()
    weekly["week_start"] = weekly["week_start"].dt.strftime("%Y-%m-%d")
    weekly.to_csv(os.path.join(out_dir, "weekly_kpis.csv"), index=False, float_format="%.4f")
    pd.DataFrame(issues, columns=["row", "problem", "action"]).to_csv(
        os.path.join(out_dir, "issues.csv"), index=False)

    def rounded(d):
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}

    summary = {
        "source": source,
        "latest_week_start": res["latest_week"].strftime("%Y-%m-%d"),
        "red_kpis": res["red_kpis"],
        "scorecard": [rounded(c) for c in res["scorecard"]],
        "queue_status": {q: {c["kpi"]: c["status"] for c in cards}
                         for q, cards in res["queue_scorecards"].items()},
        "forecasts": [rounded(f) for f in res["forecasts"]],
        "input_problems": len(issues),
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)
        handle.write("\n")


def main(argv=None):
    data = os.path.join(HERE, "data")
    parser = argparse.ArgumentParser(description="Human data operations KPI dashboard")
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate", help="write the synthetic sample data")
    g.add_argument("--data-dir", default=data)
    g.add_argument("--seed", type=int, default=5)
    r = sub.add_parser("report", help="calculate KPIs and build the dashboard")
    r.add_argument("--tasks", default=os.path.join(data, "tasks.csv"))
    r.add_argument("--workforce", default=os.path.join(data, "workforce.csv"))
    r.add_argument("--targets", default=os.path.join(data, "kpi_targets.json"))
    r.add_argument("--lookback", type=int, default=3, help="weeks averaged for the backlog outlook")
    r.add_argument("--clear-in-weeks", type=int, default=4, help="planning horizon for clearing the backlog")
    r.add_argument("--out-dir", default="out")
    args = parser.parse_args(argv)

    if args.command == "generate":
        tasks, workforce = gen.generate(args.seed)
        tasks.to_csv(os.path.join(args.data_dir, "tasks.csv"), index=False)
        workforce.to_csv(os.path.join(args.data_dir, "workforce.csv"), index=False)
        print(f"Wrote {len(tasks)} tasks and {len(workforce)} workforce rows to {args.data_dir}")
        return 0
    try:
        if args.lookback < 1 or args.clear_in_weeks < 1:
            raise ValueError("--lookback and --clear-in-weeks must be 1 or more")
        tasks, issues = load_tasks(args.tasks)
        workforce = load_workforce(args.workforce)
        targets = load_targets(args.targets)
        res = analyse(tasks, workforce, targets, args.lookback, args.clear_in_weeks)
    except (OSError, ValueError) as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 2
    source = os.path.basename(args.tasks)
    synthetic = os.path.abspath(args.tasks) == os.path.join(data, "tasks.csv")
    write_outputs(res, targets, issues, args.out_dir, source, synthetic)
    print(f"Week starting {res['latest_week']:%Y-%m-%d}, all queues:")
    for c in res["scorecard"]:
        print(f"  {c['label']:<30} {fmt(c['value'], c['format']):>10}   {STATUS_WORD[c['status']]}")
    for f in res["forecasts"]:
        clear = "not clearing" if f["weeks_to_clear"] is None else f"{f['weeks_to_clear']:.1f} weeks to clear"
        print(f"  backlog {f['queue']:<22} {f['backlog']:>6}  {f['trend']:<10} {clear}")
    print(f"{len(issues)} input problem(s). Files written to {args.out_dir}/")
    return 1 if res["red_kpis"] else 0


if __name__ == "__main__":
    sys.exit(main())
