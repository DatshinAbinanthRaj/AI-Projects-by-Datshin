"""Read ratings from CSV in long or wide layout, and report every problem found."""
import csv

LONG_COLUMNS = ("item_id", "annotator_id", "label")


def _read(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{path}: file is empty")
        header = [h.strip() for h in reader.fieldnames]
        rows = [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]
    return header, rows


def detect_layout(header):
    return "long" if all(c in header for c in LONG_COLUMNS) else "wide"


def load_ratings(path, layout="auto", allowed=None):
    """Return (units, issues).

    long layout: one row per rating, columns item_id, annotator_id, label.
    wide layout: one row per item, first column item_id, one column per annotator;
                 an empty cell means "did not label this item".
    issues is a list of {row, problem, action}; row is the spreadsheet row number.
    """
    header, rows = _read(path)
    if layout == "auto":
        layout = detect_layout(header)
    units, issues = {}, []

    def add(row_no, item, annotator, label):
        if allowed and label not in allowed:
            issues.append({"row": row_no, "problem": f"unknown label '{label}' from {annotator}",
                           "action": "rating dropped"})
            return
        ratings = units.setdefault(item, {})
        if annotator in ratings:
            same = ratings[annotator] == label
            issues.append({"row": row_no,
                           "problem": f"{annotator} rated {item} more than once"
                                      + ("" if same else f" ('{ratings[annotator]}' then '{label}')"),
                           "action": "first rating kept"})
            return
        ratings[annotator] = label

    if layout == "long":
        missing = [c for c in LONG_COLUMNS if c not in header]
        if missing:
            raise ValueError(f"{path}: missing column(s): {', '.join(missing)}")
        for n, row in enumerate(rows, start=2):
            blank = [c for c in LONG_COLUMNS if not row.get(c)]
            if blank:
                issues.append({"row": n, "problem": f"blank {', '.join(blank)}", "action": "row dropped"})
                continue
            add(n, row["item_id"], row["annotator_id"], row["label"])
    elif layout == "wide":
        if header[0] != "item_id" or len(header) < 3:
            raise ValueError(f"{path}: wide layout needs item_id first, then two or more annotator columns")
        seen = set()
        for n, row in enumerate(rows, start=2):
            item = row.get("item_id")
            if not item:
                issues.append({"row": n, "problem": "blank item_id", "action": "row dropped"})
                continue
            if item in seen:
                issues.append({"row": n, "problem": f"item {item} appears twice", "action": "row dropped"})
                continue
            seen.add(item)
            units.setdefault(item, {})
            for annotator in header[1:]:
                if row.get(annotator):
                    add(n, item, annotator, row[annotator])
    else:
        raise ValueError(f"unknown layout '{layout}'; use long, wide or auto")

    for item, ratings in units.items():
        if len(ratings) == 1:
            issues.append({"row": "", "problem": f"item {item} has one rating only",
                           "action": "kept, but cannot count towards agreement"})
    if not units:
        raise ValueError(f"{path}: no usable ratings")
    return units, issues
