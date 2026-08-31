from html import escape

STATUS_LABELS = {
    "match": "Match",
    "code_mismatch": "Code mismatch",
    "duration_mismatch": "Duration mismatch",
    "missing_in_notion": "Missing in Notion",
    "missing_in_upwork": "Missing in Upwork",
}
STATUS_CLASSES = {
    "match": "ok",
    "code_mismatch": "bad",
    "duration_mismatch": "bad",
    "missing_in_notion": "warn",
    "missing_in_upwork": "warn",
}

CSS = """
:root {
  color-scheme: dark;
  --page: #1a1a1a;
  --surface-1: #2b2b2b;
  --text-primary: #ffffff;
  --text-secondary: #cdcdcd;
  --text-muted: #adadad;
  --border: rgba(255,255,255,0.10);
  --good: #0ca30c;
  --bad: #e66767;
  --warn: #f9bc3c;
  --accent: #f9bc3c;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--page);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  padding: 40px 0 80px;
}
.wrap { max-width: 960px; margin: 0 auto; padding: 0 24px; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 16px; margin: 24px 0 8px; }
.muted { color: var(--text-muted); font-size: 12.5px; }
a { color: var(--accent); }
table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
th { color: var(--text-secondary); font-weight: 600; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.03em; }
.status { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11.5px; font-weight: 600; }
.status.ok { background: rgba(12,163,12,0.15); color: var(--good); }
.status.bad { background: rgba(230,103,103,0.15); color: var(--bad); }
.status.warn { background: rgba(249,188,60,0.15); color: var(--warn); }
.card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; margin-bottom: 20px; }
.pod-list a { display: block; padding: 10px 0; border-bottom: 1px solid var(--border); }
.pod-list a:last-child { border-bottom: none; }
"""


def _page(title, body):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{escape(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
{body}
</div>
</body>
</html>"""


def render_index(pods):
    rows = "\n".join(f'<a href="{escape(pod.slug)}/">{escape(pod.name)}</a>' for pod in pods)
    body = f"""
<h1>Pod Reconciliation</h1>
<p class="muted">Upwork time submissions checked against Notion task records, by pod.</p>
<div class="card pod-list">
{rows}
</div>
"""
    return _page("Pod Reconciliation", body)


def render_pod_page(pod, entries):
    total = len(entries)
    mismatches = sum(1 for e in entries if e.status != "match")

    rows = "\n".join(
        f"""<tr>
  <td>{escape(e.contractor)}</td>
  <td>{escape(e.date)}</td>
  <td>{escape(e.submitted_code)}</td>
  <td>{e.submitted_minutes:.0f}m</td>
  <td>{escape(e.expected_code)}</td>
  <td>{e.expected_minutes:.0f}m</td>
  <td><span class="status {STATUS_CLASSES[e.status]}">{STATUS_LABELS[e.status]}</span></td>
  <td class="muted">{escape(e.detail)}</td>
</tr>"""
        for e in sorted(entries, key=lambda e: (e.contractor, e.date))
    )

    body = f"""
<p class="muted"><a href="../">&larr; All pods</a></p>
<h1>{escape(pod.name)}</h1>
<p class="muted">{total} entries reconciled, {mismatches} need a look.</p>

<table>
<thead>
<tr>
  <th>Contractor</th>
  <th>Date</th>
  <th>Submitted code</th>
  <th>Submitted</th>
  <th>Expected code</th>
  <th>Expected</th>
  <th>Status</th>
  <th>Detail</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
"""
    return _page(pod.name, body)
