# Architecture

```
data/sample_annotations.csv   (or any export with the six required columns)
        |
        v
src/annotation_qc/qc.py
  validate()           drop or repair bad rows, list every issue
  pairwise()           every pair of annotators on the same item
  annotator_metrics()  accuracy + Wilson interval, agreement, speed, bias, flags
  batch_metrics()      accuracy and agreement per batch
  item_table()         labels per item, majority label, disputed or not
  confusion()          gold label vs label given
  analyse()            runs all of the above, returns tables + summary
        |
        +--> app.py                 Streamlit screens and Plotly charts
        +--> src/annotation_qc/report.py + run.py   Markdown, JSON and CSV files
```

## Design choices

- **All calculations live in `qc.py`.** The dashboard and the command line both call `analyse()`, so they cannot disagree, and the calculations can be tested without starting a web page.
- **Thresholds are one dataclass.** Every limit is visible in one place and adjustable from the sidebar or the command line.
- **Validation never hides data loss.** Each dropped or repaired row is listed with its spreadsheet row number and the action taken.
- **Flags need a minimum sample.** Accuracy is not judged below `min_gold` gold items, agreement not below `min_pairs` comparisons.
- **Wilson interval instead of the simple formula**, because it behaves sensibly for small samples and for results near 100%.
- **No database.** The file is analysed in memory; nothing is stored.

## Files

| Path | Purpose |
|---|---|
| `app.py` | dashboard |
| `run.py` | command line: `generate`, `check` |
| `src/annotation_qc/qc.py` | validation and metrics |
| `src/annotation_qc/report.py` | Markdown report and output files |
| `src/annotation_qc/generate.py` | synthetic data with planted problems |
| `tests/test_qc.py` | 23 tests |
| `data/` | synthetic sample, invalid sample, sample output |
