from html import escape

# CSS for reconciliation tables — merged into page.py's shared CSS, used on
# every pod's own page.
TABLE_CSS = """
h2 { font-size: 16px; margin: 32px 0 4px; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
th { color: var(--text-secondary); font-weight: 600; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.03em; }
.status { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11.5px; font-weight: 600; }
.status.ok { background: rgba(12,163,12,0.15); color: var(--good); }
.status.bad { background: rgba(230,103,103,0.15); color: var(--bad); }
"""


def _status_span(status):
    cls = "ok" if status == "match" else "bad"
    label = "Match" if status == "match" else "Mismatch"
    return f'<span class="status {cls}">{label}</span>'


def render_pod_tables(reconciliation):
    """Returns an HTML fragment (no page shell) with this one pod's two
    reconciliation tables, for embedding on that pod's own page."""
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
    ) or '<tr><td colspan="6" class="muted">No submissions yet.</td></tr>'

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
    ) or '<tr><td colspan="7" class="muted">No submissions yet.</td></tr>'

    return f"""
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
