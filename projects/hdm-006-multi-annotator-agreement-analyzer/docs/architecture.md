# Architecture

```
data/*.csv  (long: item_id, annotator_id, label   |   wide: item_id + one column per annotator)
      |
      v
src/agreement/loaders.py
  load_ratings()        -> units {item: {annotator: label}} and a list of input problems
      |
      v
src/agreement/metrics.py            pure functions, no file access
  percent_agreement()   matching pairs / all pairs
  cohen_kappa()         two annotators, items in common
  fleiss_kappa()        many annotators, equal ratings per item
  coincidence_matrix()  the table Krippendorff's alpha is built from
  krippendorff_alpha()  nominal / ordinal / interval, missing ratings allowed
      |
      v
src/agreement/analysis.py
  bootstrap_alpha()     resample items, percentile interval
  pairwise_table()      kappa for every pair, with an overlap check
  annotator_table()     mean kappa with others, alpha without the annotator
  label_table()         alpha for one label against the rest
  confusion_pairs()     which two labels meet on the same item
  item_table()          items ranked from most to least split
  analyse()             runs everything, returns one dictionary
      |
      +--> src/agreement/report.py   report.md, summary.json, five CSV tables
      +--> run.py                    arguments, error handling, exit code
```

## Design choices

- **One data shape.** Both layouts are converted to `{item: {annotator: label}}`. A missing rating is an absent key, so no placeholder value can be mistaken for a label.
- **Alpha is the headline number.** It is the only one of the three statistics that handles missing ratings, any number of annotators and ordered labels. Fleiss and Cohen are reported beside it because many teams ask for them by name.
- **Undefined is a value.** When everybody uses one label, chance agreement is 100% and the statistics cannot be calculated. Functions return `None`, the report prints `n/a`, and the exit code is 1.
- **Uncertainty is shown twice.** The interval is printed, and the reading ("reliable", "tentative", "unreliable") is given for the low end of the interval as well as the point value.
- **Small overlaps are marked.** A pair of annotators with fewer than `--min-overlap` shared items is flagged and left out of per-annotator averages.
- **Validation never hides data loss.** Every dropped row is listed with its row number and the action taken.
- **Standard library only.** The formulas are short enough to read in one sitting, and each is tested against a published example.
- **Fixed seeds.** The sample data and the bootstrap give the same result on every run.

## Files

| Path | Purpose |
|---|---|
| `run.py` | command line: `generate`, `analyse` |
| `src/agreement/metrics.py` | the four statistics |
| `src/agreement/analysis.py` | interval and breakdown tables |
| `src/agreement/loaders.py` | CSV reading and validation |
| `src/agreement/report.py` | Markdown, JSON, CSV |
| `src/agreement/generate.py` | synthetic samples with planted problems |
| `tests/test_agreement.py` | 30 tests |
| `data/` | synthetic samples, invalid samples, sample output |
