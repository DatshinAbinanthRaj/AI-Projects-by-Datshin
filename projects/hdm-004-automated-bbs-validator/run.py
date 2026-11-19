"""Command line entry point.

    python run.py generate                               # rewrite the synthetic sample data in data/
    python run.py validate data/schedules --out-dir out  # check a folder (or one file)
    python run.py validate FILE --strict                 # warnings also block release
    python run.py shapes                                 # list the shape codes in the profile
    python run.py rules                                  # list every rule and its severity

Exit codes: 0 = no schedule blocks release, 1 = at least one schedule failed or
could not be read, 2 = the command itself could not run (bad path or profile).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

from bbs_validator import generate as gen  # noqa: E402
from bbs_validator.engine import exit_code, validate_path  # noqa: E402
from bbs_validator.profile import ProfileError, load_profile  # noqa: E402
from bbs_validator.report import console_text, write_outputs  # noqa: E402
from bbs_validator.rules import RULES  # noqa: E402

DEFAULT_PROFILE = os.path.join(HERE, "data", "profile_bs8666_style.json")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Automated Bar Bending Schedule validator (prototype)")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="rule profile JSON file")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate", help="write the synthetic sample data")
    val = sub.add_parser("validate", help="check one schedule file or a folder of schedules")
    val.add_argument("path")
    val.add_argument("--out-dir", default="out")
    val.add_argument("--strict", action="store_true", help="treat REVIEW (warnings) as blocking")
    sub.add_parser("shapes", help="list the shape codes in the profile")
    sub.add_parser("rules", help="list every rule")
    args = parser.parse_args(argv)

    if args.command == "rules":
        for rule, (severity, meaning) in RULES.items():
            print(f"{severity:<8} {rule:<28} {meaning}")
        return 0

    try:
        profile = load_profile(args.profile)
    except ProfileError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.command == "shapes":
        print(f"Profile: {profile.name}")
        for code, shape in profile.shapes.items():
            print(f"{code}  {shape.description:<38} L = {shape.formula_text}")
        return 0

    if args.command == "generate":
        planted = gen.generate(profile, os.path.join(HERE, "data"))
        print(f"Sample data written to data/ with {len(planted)} planted defects (synthetic).")
        return 0

    try:
        results = validate_path(args.path, profile)
    except FileNotFoundError:
        print(f"ERROR: path not found: {args.path}", file=sys.stderr)
        return 2
    if not results:
        print(f"ERROR: no .csv or .xlsx schedules found in {args.path}", file=sys.stderr)
        return 2
    summary = write_outputs(results, profile.name, args.out_dir)
    print(console_text(results))
    print(f"\n{summary['schedules_checked']} schedule(s), {summary['bar_rows_checked']} bar rows, "
          f"{summary['errors']} error(s), {summary['warnings']} warning(s).")
    print(f"Reports written to {args.out_dir}/ (findings.csv, summary.json, report.html)")
    print("Prototype checks only: not an engineering approval or a code-compliance check.")
    return exit_code(results, args.strict)


if __name__ == "__main__":
    sys.exit(main())
