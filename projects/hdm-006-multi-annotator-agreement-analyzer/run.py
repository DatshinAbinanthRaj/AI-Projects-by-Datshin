"""Command line entry point.

    python run.py generate
    python run.py analyse data/moderation_long.csv --out-dir out
    python run.py analyse data/quality_wide.csv --level ordinal --order 1,2,3,4,5 --out-dir out

Exit code: 0 alpha meets the threshold, 1 alpha is below it or undefined, 2 the input could not be used.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

from agreement import generate as gen  # noqa: E402
from agreement.analysis import TENTATIVE, analyse  # noqa: E402
from agreement.loaders import load_ratings  # noqa: E402
from agreement.report import to_markdown, write_outputs  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="Multi-annotator agreement analyzer")
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate", help="write the synthetic sample data")
    g.add_argument("--data-dir", default=os.path.join(HERE, "data"))
    a = sub.add_parser("analyse", help="measure agreement in a ratings file")
    a.add_argument("csv")
    a.add_argument("--layout", choices=["auto", "long", "wide"], default="auto")
    a.add_argument("--level", choices=["nominal", "ordinal", "interval"], default="nominal")
    a.add_argument("--order", help="ordinal only: labels from lowest to highest, comma-separated")
    a.add_argument("--labels", help="allowed labels, comma-separated; others are dropped and listed")
    a.add_argument("--min-alpha", type=float, default=TENTATIVE, help="threshold for exit code 0")
    a.add_argument("--min-overlap", type=int, default=10, help="items two annotators must share")
    a.add_argument("--bootstrap", type=int, default=1000, help="bootstrap repetitions (0 to skip)")
    a.add_argument("--seed", type=int, default=7)
    a.add_argument("--out-dir", default="out")
    args = parser.parse_args(argv)

    if args.command == "generate":
        gen.write_all(args.data_dir)
        print(f"Wrote sample data to {args.data_dir}")
        return 0
    try:
        order = [x.strip() for x in args.order.split(",")] if args.order else None
        allowed = [x.strip() for x in args.labels.split(",")] if args.labels else order
        units, issues = load_ratings(args.csv, args.layout, allowed)
        res = analyse(units, args.level, order, args.bootstrap, args.seed, args.min_overlap)
    except (OSError, ValueError) as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 2
    source = os.path.basename(args.csv)
    write_outputs(res, issues, args.out_dir, source)
    print(to_markdown(res, source, issues))
    print(f"Files written to {args.out_dir}/")
    alpha = res["summary"]["krippendorff_alpha"]
    return 0 if alpha is not None and alpha >= args.min_alpha else 1


if __name__ == "__main__":
    sys.exit(main())
