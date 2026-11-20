"""Build the dashboard as one HTML file with inline SVG charts. No scripts, no downloads."""
import html
import math

STATUS_WORD = {"green": "On target", "amber": "Watch", "red": "Off target", "no data": "No data"}
SERIES_COLOURS = ["#2563eb", "#d97706", "#059669", "#7c3aed"]

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--muted:#5d6878;--line:#dfe3e8;
--green:#157f3b;--amber:#a15c00;--red:#b42318;--nodata:#5d6878}
@media (prefers-color-scheme:dark){:root{--bg:#12161c;--card:#1b212a;--ink:#e8ecf1;--muted:#9aa6b5;
--line:#2f3844;--green:#4ade80;--amber:#fbbf24;--red:#f87171;--nodata:#9aa6b5}}
*{box-sizing:border-box}body{margin:0;padding:24px 16px;background:var(--bg);color:var(--ink);
font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:1100px;margin:auto}
h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 10px}.muted{color:var(--muted)}
.note{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--amber);
padding:8px 12px;border-radius:6px;margin:12px 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
.tile{background:var(--card);border:1px solid var(--line);border-top:4px solid var(--nodata);
border-radius:8px;padding:12px}.tile .v{font-size:26px;font-weight:650}
.tile .s{font-weight:600;font-size:13px}
.green{border-top-color:var(--green)}.amber{border-top-color:var(--amber)}.red{border-top-color:var(--red)}
.t-green{color:var(--green)}.t-amber{color:var(--amber)}.t-red{color:var(--red)}.t-nodata{color:var(--nodata)}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,430px),1fr));gap:12px}
.chart{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.chart h3{font-size:14px;margin:0 0 6px}svg{width:100%;height:auto;display:block}
svg text{fill:var(--muted);font-size:12px}.legend{font-size:12px;color:var(--muted)}
.legend b{font-weight:400;white-space:nowrap;margin-right:12px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px}
.scroll{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:7px 10px;text-align:right;
border-bottom:1px solid var(--line);white-space:nowrap}th:first-child,td:first-child{text-align:left}
th{color:var(--muted);font-weight:600}tr:last-child td{border-bottom:0}
"""


def fmt(value, kind):
    if value is None:
        return "n/a"
    if kind == "pct":
        return f"{value * 100:.1f}%"
    if kind == "hours":
        return f"{value:.1f} h"
    if kind == "money":
        return f"{value:.2f}"
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.1f}"


def fmt_change(card):
    change = card["change"]
    if change is None:
        return "no previous week"
    if card["format"] == "pct":
        text = f"{change * 100:+.1f} pts"
    elif card["format"] == "hours":
        text = f"{change:+.1f} h"
    elif card["format"] == "money":
        text = f"{change:+.2f}"
    else:
        text = f"{change:+,.0f}"
    if change == 0:
        return f"{text} vs previous week"
    better = (change > 0) == (card["direction"] == "higher")
    return f"{text} vs previous week ({'better' if better else 'worse'})"


def line_chart(labels, series, kind="number", target=None, width=520, height=210):
    """series: list of (name, [values or None]). Returns an SVG string."""
    left, right, top, bottom = 52, 24, 12, 28
    values = [v for _, vals in series for v in vals if v is not None]
    if target is not None:
        values.append(target)
    if not values:
        return "<p class='muted'>No data.</p>"
    low, high = min(values), max(values)
    low = 0 if kind != "pct" else max(0, low - 0.05)
    high = min(1, high + 0.02) if kind == "pct" else high * 1.1 or 1
    if kind == "number":
        high = math.ceil(high / 4) * 4          # whole numbers on the axis
    if high == low:
        high = low + 1
    plot_w, plot_h = width - left - right, height - top - bottom

    def x(i):
        return left + (plot_w * i / (len(labels) - 1) if len(labels) > 1 else plot_w / 2)

    def y(v):
        return top + plot_h * (1 - (v - low) / (high - low))

    parts = [f"<svg viewBox='0 0 {width} {height}' role='img'>"]
    for step in range(5):
        v = low + (high - low) * step / 4
        parts.append(f"<line x1='{left}' x2='{width - right}' y1='{y(v):.1f}' y2='{y(v):.1f}' "
                     f"stroke='var(--line)'/><text x='{left - 6}' y='{y(v) + 4:.1f}' "
                     f"text-anchor='end'>{fmt(v, kind)}</text>")
    for i, label in enumerate(labels):
        parts.append(f"<text x='{x(i):.1f}' y='{height - 8}' text-anchor='middle'>{html.escape(label)}</text>")
    if target is not None:
        parts.append(f"<line x1='{left}' x2='{width - right}' y1='{y(target):.1f}' y2='{y(target):.1f}' "
                     f"stroke='var(--muted)' stroke-dasharray='5 4'/>"
                     f"<text x='{width - right}' y='{y(target) - 4:.1f}' text-anchor='end'>target</text>")
    for n, (name, vals) in enumerate(series):
        colour = SERIES_COLOURS[n % len(SERIES_COLOURS)]
        points = [(x(i), y(v)) for i, v in enumerate(vals) if v is not None]
        if len(points) > 1:
            path = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)
            parts.append(f"<polyline points='{path}' fill='none' stroke='{colour}' stroke-width='2'/>")
        for (px, py), v in zip(points, [v for v in vals if v is not None]):
            parts.append(f"<circle cx='{px:.1f}' cy='{py:.1f}' r='3' fill='{colour}'>"
                         f"<title>{html.escape(name)}: {fmt(v, kind)}</title></circle>")
    parts.append("</svg>")
    if len(series) > 1:
        parts.append("<div class='legend'>" + "".join(
            f"<b><i style='background:{SERIES_COLOURS[n % len(SERIES_COLOURS)]}'></i>{html.escape(name)}</b>"
            for n, (name, _) in enumerate(series)) + "</div>")
    return "".join(parts)


def _table(headers, rows):
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<div class='scroll'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def _status_cell(card):
    cls = card["status"].replace(" ", "")
    return (f"{fmt(card['value'], card['format'])} "
            f"<span class='t-{cls}'>({STATUS_WORD[card['status']]})</span>")


def _values(frame, column):
    return [None if v is None or v != v else float(v) for v in frame[column]]


def build(res, targets, issues, source, synthetic=False):
    weekly = res["weekly"]
    overall = weekly[weekly["queue"] == "ALL"].sort_values("week_start")
    labels = [d.strftime("%d %b") for d in overall["week_start"]]
    queues = sorted(q for q in weekly["queue"].unique() if q != "ALL")
    latest = res["latest_week"]
    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Human Data Operations KPIs</title><style>{CSS}</style></head><body><main>",
           "<h1>Human Data Operations KPIs</h1>",
           f"<div class='muted'>Source: {html.escape(source)} &middot; week starting "
           f"{latest.strftime('%d %b %Y')} compared with targets &middot; {len(overall)} weeks of history</div>",
           "<div class='note'>" + ("Synthetic sample data. " if synthetic else "")
           + "A status is a prompt to investigate, not a judgement about a team.</div>"]

    out.append("<h2>Latest week against targets (all queues)</h2><div class='tiles'>")
    for card in res["scorecard"]:
        cls = card["status"].replace(" ", "")
        sign = "at least" if card["direction"] == "higher" else "at most"
        out.append(f"<div class='tile {cls}'><div class='muted'>{html.escape(card['label'])}</div>"
                   f"<div class='v'>{fmt(card['value'], card['format'])}</div>"
                   f"<div class='s t-{cls}'>{STATUS_WORD[card['status']]}</div>"
                   f"<div class='muted'>Target {sign} {fmt(card['target'], card['format'])}</div>"
                   f"<div class='muted'>{fmt_change(card)}</div></div>")
    out.append("</div>")

    def per_queue(column):
        return [(q, _values(weekly[weekly["queue"] == q].sort_values("week_start"), column)) for q in queues]

    charts = [
        ("Tasks arriving and completed per week",
         line_chart(labels, [("Arrivals", _values(overall, "arrivals")),
                             ("Completed", _values(overall, "completed"))])),
        ("Backlog at end of week, by queue", line_chart(labels, per_queue("backlog_end"))),
        ("SLA compliance, by queue",
         line_chart(labels, per_queue("sla_compliance"), "pct", targets.get("sla_compliance", {}).get("target"))),
        ("QA pass rate, by queue",
         line_chart(labels, per_queue("qa_pass_rate"), "pct", targets.get("qa_pass_rate", {}).get("target"))),
    ]
    out.append("<h2>Trends</h2><div class='charts'>")
    out += [f"<div class='chart'><h3>{html.escape(t)}</h3>{svg}</div>" for t, svg in charts]
    out.append("</div>")

    out.append("<h2>Latest week by queue</h2>")
    first = res["scorecard"]
    out.append(_table(["Queue"] + [c["label"] for c in first],
                      [[html.escape(q)] + [_status_cell(c) for c in res["queue_scorecards"][q]] for q in queues]))

    out.append(f"<h2>Backlog outlook (average of the last {res['forecasts'][0]['weeks_used']} weeks)</h2>")
    rows = []
    for f in res["forecasts"]:
        clear = "n/a" if f["weeks_to_clear"] is None else f"{f['weeks_to_clear']:.1f}"
        extra = "n/a" if f["extra_paid_hours_per_week"] is None else f"{f['extra_paid_hours_per_week']:.0f}"
        rows.append([html.escape("All queues" if f["queue"] == "ALL" else f["queue"]),
                     f"{f['backlog']:,}", f"{f['avg_arrivals']:,.0f}", f"{f['avg_completed']:,.0f}",
                     f"{round(f['net_per_week']):+,}", f["trend"], clear, extra])
    out.append(_table(["Queue", "Backlog now", "Arrivals / week", "Completed / week", "Net / week",
                       "Trend", "Weeks to clear", f"Extra paid hours / week to clear in "
                       f"{res['forecasts'][0]['clear_in_weeks']} weeks"], rows))
    out.append("<p class='muted'>The outlook assumes the next weeks look like the last ones. "
               "It is arithmetic on averages, not a prediction model.</p>")

    out.append(f"<h2>Input problems ({len(issues)})</h2>")
    if issues:
        out.append(_table(["Row", "Problem", "Action"],
                          [[str(i["row"]), html.escape(i["problem"]), html.escape(i["action"])]
                           for i in issues[:25]]))
        if len(issues) > 25:
            out.append(f"<p class='muted'>...and {len(issues) - 25} more in issues.csv.</p>")
    else:
        out.append("<p class='muted'>None.</p>")
    out.append("</main></body></html>")
    return "".join(out)
