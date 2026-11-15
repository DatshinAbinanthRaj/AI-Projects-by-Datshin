"""Entry point: python run.py <command>  (see README)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from rebar_qa.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
