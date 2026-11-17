"""Command line entry point.

    python run.py generate                 # write the synthetic sample data to data/
    python run.py score --out-dir out      # score the sample data
    python run.py score --rubric R --cases C --responses P --scores S --out-dir out
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

from llm_eval import generate as gen  # noqa: E402
from llm_eval.compare import model_summary, paired_comparison  # noqa: E402
from llm_eval.loaders import load_cases, load_human_scores, load_responses  # noqa: E402
from llm_eval.report import to_markdown, write_outputs  # noqa: E402
from llm_eval.rubric import load_rubric  # noqa: E402
from llm_eval.scoring import score_all  # noqa: E402


def evaluate(rubric_path, cases_path, responses_path, scores_path=None, seed=7):
    """Run the whole pipeline and return everything the reports need."""
    rubric = load_rubric(rubric_path)
    cases = load_cases(cases_path)
    responses, issues = load_responses(responses_path, cases)
    human = {}
    if scores_path:
        human, score_issues = load_human_scores(scores_path, rubric, responses)
        issues += score_issues
    results = score_all(rubric, cases, responses, human)
    summaries = model_summary(rubric, results)
    models = [s["model"] for s in summaries]
    comparison = paired_comparison(results, models[0], models[1], seed=seed) if len(models) == 2 else None
    return rubric, results, summaries, comparison, issues


def main(argv=None):
    data = os.path.join(HERE, "data")
    parser = argparse.ArgumentParser(description="LLM response evaluation and scoring engine")
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate", help="write synthetic sample data")
    g.add_argument("--data-dir", default=data)
    g.add_argument("--seed", type=int, default=3)
    s = sub.add_parser("score", help="score responses against a rubric")
    s.add_argument("--rubric", default=os.path.join(data, "rubric.json"))
    s.add_argument("--cases", default=os.path.join(data, "test_cases.jsonl"))
    s.add_argument("--responses", default=os.path.join(data, "responses.csv"))
    s.add_argument("--scores", default=os.path.join(data, "human_scores.csv"),
                   help="human ratings CSV; pass an empty string to run automated checks only")
    s.add_argument("--out-dir", default="out")
    s.add_argument("--seed", type=int, default=7, help="seed for the bootstrap interval")
    args = parser.parse_args(argv)

    if args.command == "generate":
        n_cases, n_resp, n_scores = gen.write_sample(args.data_dir, args.seed)
        print(f"Wrote {n_cases} test cases, {n_resp} responses and {n_scores} ratings to {args.data_dir}")
        return 0
    try:
        rubric, results, summaries, comparison, issues = evaluate(
            args.rubric, args.cases, args.responses, args.scores or None, args.seed)
    except (OSError, ValueError) as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 2
    write_outputs(args.out_dir, rubric, results, summaries, comparison, issues)
    print(to_markdown(rubric, results, summaries, comparison, issues))
    print(f"Files written to {args.out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
