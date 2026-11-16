"""Streamlit dashboard.  Run with:  streamlit run app.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from annotation_qc.qc import Thresholds, analyse  # noqa: E402
from annotation_qc.report import pct, to_markdown  # noqa: E402

BLUE, RED, MUTED, GRID = "#2a78d6", "#d03b3b", "#898781", "#e1e0d9"
SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sample_annotations.csv")

st.set_page_config(page_title="Annotation QC", layout="wide")
st.title("Annotation Quality Control Dashboard")
st.caption("Prototype. The built-in sample is synthetic data with planted problems. "
           "A flag is a reason to look closer, not a verdict about a person.")

with st.sidebar:
    st.header("Data")
    upload = st.file_uploader("Annotation export (CSV)", type="csv")
    labels_text = st.text_input("Allowed labels (comma-separated, optional)", "")
    st.header("Thresholds")
    th = Thresholds(
        min_accuracy=st.slider("Minimum gold accuracy", 0.5, 1.0, 0.80, 0.01),
        min_gold=st.number_input("Gold items needed to judge accuracy", 1, 500, 10),
        min_agreement=st.slider("Minimum agreement with peers", 0.3, 1.0, 0.70, 0.01),
        min_pairs=st.number_input("Comparisons needed to judge agreement", 1, 1000, 20),
        min_speed_ratio=st.slider("Minimum speed ratio (vs team median time)", 0.1, 1.0, 0.40, 0.05),
        max_label_bias=st.slider("Maximum label bias", 0.05, 0.6, 0.20, 0.01),
    )

source = upload if upload is not None else SAMPLE
name = upload.name if upload is not None else "sample_annotations.csv (synthetic)"
try:
    raw = pd.read_csv(source, dtype=str, keep_default_na=False)
    allowed = [x.strip() for x in labels_text.split(",") if x.strip()] or None
    res = analyse(raw, th, allowed)
except ValueError as err:
    st.error(f"Cannot analyse this file: {err}")
    st.stop()

s, annot = res["summary"], res["annotators"]
st.subheader(f"Overview: {name}")
tiles = st.columns(5)
tiles[0].metric("Labels used", f"{s['rows_used']} / {s['rows_received']}")
tiles[1].metric("Gold accuracy", pct(s["gold_accuracy"]))
tiles[2].metric("Pairwise agreement", pct(s["agreement_rate"]))
tiles[3].metric("Disputed items", f"{s['disputed_items']} ({pct(s['disputed_share'])})")
tiles[4].metric("Flagged annotators", f"{len(s['flagged_annotators'])} of {s['annotators']}")


def bar_chart(frame, x, y, title, threshold=None, flag_text=None, error=None):
    """Single-measure bar chart. Bars below the threshold are red AND labelled."""
    values = frame[y].astype(float)
    below = values < threshold if threshold is not None else pd.Series(False, index=frame.index)
    text = [f"{v * 100:.0f}%" + (f" {flag_text}" if b and flag_text else "") if pd.notna(v) else "n/a"
            for v, b in zip(values, below)]
    fig = go.Figure(go.Bar(
        x=frame[x], y=values, text=text, textposition="inside", insidetextanchor="start", textangle=0,
        constraintext="none", textfont=dict(color="#ffffff", size=11),
        marker_color=[RED if b else BLUE for b in below], width=0.62, error_y=error,
        hovertemplate="%{x}: %{y:.1%}<extra></extra>"))
    if threshold is not None:
        fig.add_hline(y=threshold, line_dash="dot", line_color=MUTED)
        title = f"{title}<br><sup>dotted line = {threshold:.0%} threshold</sup>"
    fig.update_layout(title=title, height=340, margin=dict(l=10, r=10, t=70, b=10),
                      yaxis=dict(range=[0, 1.05], tickformat=".0%", gridcolor=GRID),
                      xaxis=dict(type="category"), showlegend=False,
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


tab_people, tab_batches, tab_confusion, tab_items, tab_issues = st.tabs(
    ["Annotators", "Batches", "Confusion", f"Disputed items ({s['disputed_items']})",
     f"Validation issues ({s['validation_issues']})"])

with tab_people:
    left, right = st.columns(2)
    judged = annot[annot["gold_items"] > 0]
    if not judged.empty:
        err = dict(type="data", symmetric=False, color=MUTED, thickness=1.5,
                   array=(judged["accuracy_ci_high"] - judged["gold_accuracy"]).astype(float),
                   arrayminus=(judged["gold_accuracy"] - judged["accuracy_ci_low"]).astype(float))
        left.plotly_chart(bar_chart(judged, "annotator_id", "gold_accuracy",
                                    "Gold accuracy (lines show the 95% interval)",
                                    th.min_accuracy, "LOW", err), width="stretch")
    else:
        left.info("No gold items in this file, so accuracy cannot be measured.")
    compared = annot[annot["comparisons"] > 0]
    if not compared.empty:
        right.plotly_chart(bar_chart(compared, "annotator_id", "agreement_rate", "Agreement with peers",
                                     th.min_agreement, "LOW"), width="stretch")
    show = annot.copy()
    for col in ["gold_accuracy", "accuracy_ci_low", "accuracy_ci_high", "agreement_rate", "label_bias"]:
        show[col] = show[col].map(pct)
    st.dataframe(show, width="stretch", hide_index=True)

with tab_batches:
    batches = res["batches"]
    left, right = st.columns(2)
    if batches["gold_accuracy"].notna().any():
        left.plotly_chart(bar_chart(batches, "batch", "gold_accuracy", "Gold accuracy by batch",
                                    th.min_accuracy, "LOW"), width="stretch")
    if batches["agreement_rate"].notna().any():
        right.plotly_chart(bar_chart(batches, "batch", "agreement_rate", "Agreement by batch",
                                     th.min_agreement, "LOW"), width="stretch")
    st.dataframe(batches, width="stretch", hide_index=True)

with tab_confusion:
    conf = res["confusion"]
    if conf.empty:
        st.info("No gold items in this file.")
    else:
        fig = go.Figure(go.Heatmap(
            z=conf.values, x=list(conf.columns), y=list(conf.index), text=conf.values,
            texttemplate="%{text}", colorscale=[[0, "#f3f7fd"], [0.5, "#86b6ef"], [1, "#184f95"]],
            xgap=2, ygap=2, colorbar=dict(title="labels"),
            hovertemplate="correct: %{y}<br>given: %{x}<br>count: %{z}<extra></extra>"))
        fig.update_layout(title="Correct label (rows) vs label given (columns), gold items only",
                          height=420, yaxis=dict(autorange="reversed", type="category"),
                          xaxis=dict(type="category"), margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width="stretch")
        st.dataframe(conf, width="stretch")

with tab_items:
    items = res["items"]
    st.write("Items where annotators gave different labels. These are the ones to send for adjudication.")
    st.dataframe(items[items["disputed"]].drop(columns="disputed"), width="stretch", hide_index=True)

with tab_issues:
    if res["issues"].empty:
        st.success("No validation issues.")
    else:
        st.dataframe(res["issues"], width="stretch", hide_index=True)

st.download_button("Download report (Markdown)", to_markdown(res, name), file_name="annotation_qc_report.md")
