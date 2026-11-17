"""Read the input files and report every data problem instead of hiding it.

Hard problems (missing columns, duplicate ids, empty files) raise ValueError.
Row-level problems drop that row and add a line to the `issues` list.
"""
import csv
import json


def load_cases(path):
    """Read test cases from a JSON Lines file (one JSON object per line)."""
    cases = {}
    with open(path, encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as err:
                raise ValueError(f"test cases line {line_no} is not valid JSON: {err}") from err
            cid = str(case.get("case_id", "")).strip()
            if not cid:
                raise ValueError(f"test cases line {line_no} has no case_id")
            if cid in cases:
                raise ValueError(f"test case id '{cid}' appears twice")
            for key in ("required_facts", "forbidden_phrases"):
                if not isinstance(case.get(key, []), list):
                    raise ValueError(f"test case '{cid}': {key} must be a list")
            max_words = case.get("max_words")
            if max_words is not None and (not isinstance(max_words, int) or max_words <= 0):
                raise ValueError(f"test case '{cid}': max_words must be a whole number above 0")
            cases[cid] = case
    if not cases:
        raise ValueError("test cases file is empty")
    return cases


def _read_csv(path, required_columns, label):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        columns = reader.fieldnames or []
        missing = [c for c in required_columns if c not in columns]
        if missing:
            raise ValueError(f"{label} file is missing column(s): {', '.join(missing)}")
        return list(reader)


def load_responses(path, cases):
    """Return ({(case_id, model): text}, issues)."""
    rows = _read_csv(path, ("case_id", "model", "response"), "responses")
    responses, issues = {}, []
    for row_no, row in enumerate(rows, start=2):
        cid, model = (row["case_id"] or "").strip(), (row["model"] or "").strip()
        text = row["response"] or ""
        if not cid or not model:
            issues.append(f"responses row {row_no}: empty case_id or model, row dropped")
        elif cid not in cases:
            issues.append(f"responses row {row_no}: unknown case_id '{cid}', row dropped")
        elif (cid, model) in responses:
            raise ValueError(f"responses row {row_no}: duplicate response for {cid} / {model}")
        elif not text.strip():
            issues.append(f"responses row {row_no}: empty response for {cid} / {model}, row dropped")
        else:
            responses[(cid, model)] = text
    if not responses:
        raise ValueError("responses file has no usable rows")
    return responses, issues


def load_human_scores(path, rubric, responses):
    """Return ({(case_id, model): {criterion: {evaluator: score}}}, issues)."""
    rows = _read_csv(path, ("case_id", "model", "evaluator", "criterion", "score"), "human scores")
    scores, issues = {}, []
    valid_criteria = set(rubric.criterion_ids)
    for row_no, row in enumerate(rows, start=2):
        cid, model = (row["case_id"] or "").strip(), (row["model"] or "").strip()
        evaluator, crit = (row["evaluator"] or "").strip(), (row["criterion"] or "").strip()
        where = f"human scores row {row_no}"
        if (cid, model) not in responses:
            issues.append(f"{where}: no response for {cid} / {model}, row dropped")
            continue
        if crit not in valid_criteria:
            issues.append(f"{where}: criterion '{crit}' is not in the rubric, row dropped")
            continue
        if not evaluator:
            issues.append(f"{where}: empty evaluator, row dropped")
            continue
        try:
            value = float(row["score"])
        except (TypeError, ValueError):
            issues.append(f"{where}: score '{row['score']}' is not a number, row dropped")
            continue
        if not rubric.scale_min <= value <= rubric.scale_max:
            issues.append(f"{where}: score {row['score']} is outside the "
                          f"{rubric.scale_min}-{rubric.scale_max} scale, row dropped")
            continue
        by_eval = scores.setdefault((cid, model), {}).setdefault(crit, {})
        if evaluator in by_eval:
            issues.append(f"{where}: {evaluator} already scored {crit} for {cid} / {model}, "
                          "first score kept")
            continue
        by_eval[evaluator] = value
    return scores, issues
