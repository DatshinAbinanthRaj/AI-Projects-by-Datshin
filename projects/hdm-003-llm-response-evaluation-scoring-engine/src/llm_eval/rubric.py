"""Load and validate a scoring rubric.

A rubric is a JSON file: a rating scale, a pass mark, and a list of criteria.
Each criterion has a weight (all weights add up to 1) and may be marked
"critical", which means a low rating on it fails the response on its own.
"""
import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Criterion:
    id: str
    description: str
    weight: float
    critical: bool = False
    critical_min: float = 0.0


@dataclass(frozen=True)
class Rubric:
    name: str
    scale_min: int
    scale_max: int
    pass_score: float
    criteria: tuple
    disagreement_gap: int = 2
    auto_links: dict = field(default_factory=dict)

    @property
    def criterion_ids(self):
        return [c.id for c in self.criteria]


def parse_rubric(raw):
    """Turn a dict into a Rubric. Raises ValueError listing every problem found."""
    problems = []
    if not isinstance(raw, dict):
        raise ValueError("rubric must be a JSON object")
    for key in ("name", "scale_min", "scale_max", "pass_score", "criteria"):
        if key not in raw:
            problems.append(f"missing field '{key}'")
    if problems:
        raise ValueError("invalid rubric: " + "; ".join(problems))

    lo, hi, pass_score = raw["scale_min"], raw["scale_max"], raw["pass_score"]
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (lo, hi)):
        problems.append("scale_min and scale_max must be whole numbers")
    elif lo >= hi:
        problems.append("scale_min must be lower than scale_max")
    if not isinstance(pass_score, (int, float)) or not 0 <= pass_score <= 100:
        problems.append("pass_score must be between 0 and 100")

    criteria, seen, weights = [], set(), []
    items = raw["criteria"]
    if not isinstance(items, list) or not items:
        problems.append("criteria must be a non-empty list")
        items = []
    for n, item in enumerate(items, start=1):
        cid = str(item.get("id", "")).strip() if isinstance(item, dict) else ""
        if not cid:
            problems.append(f"criterion {n} has no id")
            continue
        if cid in seen:
            problems.append(f"criterion id '{cid}' is used twice")
            continue
        seen.add(cid)
        weight = item.get("weight")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight <= 0:
            problems.append(f"criterion '{cid}' needs a weight above 0")
            continue
        weights.append(float(weight))
        critical = bool(item.get("critical", False))
        critical_min = item.get("critical_min", lo if isinstance(lo, int) else 0)
        if critical and isinstance(lo, int) and isinstance(hi, int):
            if not isinstance(critical_min, (int, float)) or not lo <= critical_min <= hi:
                problems.append(f"criterion '{cid}' critical_min must be inside the scale")
                continue
        criteria.append(Criterion(cid, str(item.get("description", "")), float(weight),
                                  critical, float(critical_min)))
    if weights:
        total = sum(weights)
        if abs(total - 1.0) > 1e-6:
            problems.append(f"weights add up to {total:.4f}, they must add up to 1")

    gap = raw.get("disagreement_gap", 2)
    if not isinstance(gap, int) or isinstance(gap, bool) or gap < 1:
        problems.append("disagreement_gap must be a whole number of 1 or more")
    links = raw.get("auto_links", {})
    if not isinstance(links, dict):
        problems.append("auto_links must be an object")
        links = {}
    for check, cid in links.items():
        if check not in ("fact_coverage", "forbidden_content"):
            problems.append(f"auto_links has unknown check '{check}'")
        elif cid not in seen:
            problems.append(f"auto_links points to unknown criterion '{cid}'")

    if problems:
        raise ValueError("invalid rubric: " + "; ".join(problems))
    return Rubric(str(raw["name"]), lo, hi, float(pass_score), tuple(criteria), gap, dict(links))


def load_rubric(path):
    with open(path, encoding="utf-8") as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as err:
            raise ValueError(f"rubric file is not valid JSON: {err}") from err
    return parse_rubric(raw)
