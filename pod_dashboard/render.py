from html import escape

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
h2 { font-size: 16px; margin: 32px 0 4px; }
.muted { color: var(--text-muted); font-size: 12.5px; }
a { color: var(--accent); }
table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
th { color: var(--text-secondary); font-weight: 600; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.03em; }
.status { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11.5px; font-weight: 600; }
.status.ok { background: rgba(12,163,12,0.15); color: var(--good); }
.status.bad { background: rgba(230,103,103,0.15); color: var(--bad); }
.card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; margin-bottom: 20px; }
.pod-list a { display: block; padding: 10px 0; border-bottom: 1px solid var(--border); }
.pod-list a:last-child { border-bottom: none; }
.warning { background: rgba(249,188,60,0.12); border: 1px solid rgba(249,188,60,0.3); border-radius: 8px; padding: 10px 14px; font-size: 12.5px; color: var(--warn); margin-top: 16px; }
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


def _status_span(status):
    cls = "ok" if status == "match" else "bad"
    label = "Match" if status == "match" else "Mismatch"
    return f'<span class="status {cls}">{label}</span>'


def render_index(pods, unknown_handles=None):
    rows = "\n".join(f'<a href="{escape(pod.slug)}/">{escape(pod.name)}</a>' for pod in pods)

    unknown_warning = ""
    if unknown_handles:
        handles = ", ".join(escape(h) for h in unknown_handles)
        unknown_warning = f'<div class="warning">Upwork submissions from handle(s) not found in any pod\'s roster: {handles}</div>'

    body = f"""
<h1>Pod Reconciliation</h1>
<p class="muted">Upwork time submissions checked against Notion task records, by pod.</p>
<div class="card pod-list">
{rows}
</div>
{unknown_warning}
"""
    return _page("Pod Reconciliation", body)


def render_pod_page(pod, reconciliation):
    hours_mismatches = sum(1 for c in reconciliation.hours_checks if c.status == "mismatch")
    code_mismatches = sum(1 for c in reconciliation.code_checks if c.status == "mismatch")

    hours_rows = "\n".join(
        f"""<tr>
  <td>{escape(c.contractor)}</td>
  <td>{escape(c.date_from)} &rarr; {escape(c.date_to)}</td>
  <td>{c.submitted_minutes:.0f}m</td>
  <td>{c.expected_minutes:.0f}m</td>
  <td>{_status_span(c.status)}</td>
  <td class="muted">{escape(c.detail)}</td>
</tr>"""
        for c in sorted(reconciliation.hours_checks, key=lambda c: (c.contractor, c.date_from))
    )

    code_rows = "\n".join(
        f"""<tr>
  <td>{escape(c.contractor)}</td>
  <td>{escape(c.date_from)} &rarr; {escape(c.date_to)}</td>
  <td>{escape(c.code)}<br><span class="muted">{escape(c.label) if c.label else '(unrecognized)'}</span></td>
  <td>{c.upwork_count}</td>
  <td>{c.notion_count}</td>
  <td>{_status_span(c.status)}</td>
  <td class="muted">{escape(c.detail)}</td>
</tr>"""
        for c in sorted(reconciliation.code_checks, key=lambda c: (c.contractor, c.date_from, c.code))
    )

    body = f"""
<p class="muted"><a href="../">&larr; All pods</a></p>
<h1>{escape(pod.name)}</h1>
<p class="muted">{hours_mismatches} hours mismatch(es), {code_mismatches} code-count mismatch(es).</p>

<h2>Submitted time vs. code stamps</h2>
<p class="muted">Does each submission's total time match what its logged codes add up to?</p>
<table>
<thead><tr><th>Contractor</th><th>Period</th><th>Submitted</th><th>Expected</th><th>Status</th><th>Detail</th></tr></thead>
<tbody>
{hours_rows}
</tbody>
</table>

<h2>Upwork codes vs. Notion records</h2>
<p class="muted">Does the number of times each code was submitted on Upwork match how many times Notion shows it completed?</p>
<table>
<thead><tr><th>Contractor</th><th>Period</th><th>Code</th><th>Upwork</th><th>Notion</th><th>Status</th><th>Detail</th></tr></thead>
<tbody>
{code_rows}
</tbody>
</table>
"""
    return _page(pod.name, body)
