"""Command line entry point.

    python run.py generate                      # write the synthetic sample data
    python run.py check data/sample_annotations.csv --out-dir out
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import pandas as pd  # noqa: E402

from annotation_qc import generate as gen  # noqa: E402
from annotation_qc.qc import Thresholds, analyse  # noqa: E402
from annotation_qc.report import to_markdown, write_outputs  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="Annotation quality control")
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate", help="write synthetic sample data")
    g.add_argument("--out", default="data/sample_annotations.csv")
    g.add_argument("--seed", type=int, default=11)
    c = sub.add_parser("check", help="analyse an annotation export")
    c.add_argument("csv")
    c.add_argument("--out-dir", default="out")
    c.add_argument("--labels", help="comma-separated allowed labels (optional)")
    c.add_argument("--min-accuracy", type=float, default=Thresholds.min_accuracy)
    c.add_argument("--min-agreement", type=float, default=Thresholds.min_agreement)
    args = parser.parse_args(argv)

    if args.command == "generate":
        gen.generate(seed=args.seed).to_csv(args.out, index=False)
        print(f"Wrote {args.out}")
        return 0
    try:
        raw = pd.read_csv(args.csv, dtype=str, keep_default_na=False)
        th = Thresholds(min_accuracy=args.min_accuracy, min_agreement=args.min_agreement)
        res = analyse(raw, th, args.labels.split(",") if args.labels else None)
    except (OSError, ValueError) as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 2
    write_outputs(res, args.out_dir, os.path.basename(args.csv))
    print(to_markdown(res, os.path.basename(args.csv)))
    print(f"Files written to {args.out_dir}/")
    return 1 if res["summary"]["flagged_annotators"] else 0


if __name__ == "__main__":
    sys.exit(main())
