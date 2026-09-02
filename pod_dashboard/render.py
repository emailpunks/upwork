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
.status.neutral { background: rgba(255,255,255,0.06); color: var(--text-secondary); }
.period-line { font-weight: 700; color: var(--text-primary); font-size: 13px; margin: 4px 0 0; }
"""


def _status_span(status):
    cls = "ok" if status == "match" else "bad"
    label = "Match" if status == "match" else "Mismatch"
    return f'<span class="status {cls}">{label}</span>'


def render_notion_master_list(notion_codes, used_codes):
    """notion_codes: the flat set of every code pulled from Notion for this
    pod (the "master list"). used_codes: this pod's ledger (see ledger.py)
    — a code's claims dict is {contractor_name: period_string, ...}, empty
    if nobody's claimed it yet. Returns an HTML fragment for embedding on
    the pod's own page — this is the audit view of the whole master list,
    independent of any particular CSV run."""
    rows = []
    for code in sorted(notion_codes):
        claims = used_codes.get(code, {})
        if claims:
            status_html = '<span class="status ok">Claimed</span>'
            detail = "; ".join(f"{name} ({period})" for name, period in sorted(claims.items()))
        else:
            status_html = '<span class="status neutral">Unclaimed</span>'
            detail = "not yet claimed by anyone"
        rows.append(
            f"""<tr>
  <td>{escape(code)}</td>
  <td>{status_html}</td>
  <td class="muted">{escape(detail)}</td>
</tr>"""
        )

    rows_html = "\n".join(rows) or '<tr><td colspan="3" class="muted">No codes pulled from Notion yet.</td></tr>'
    claimed_count = sum(1 for code in notion_codes if used_codes.get(code))

    return f"""
<h2>Notion master list</h2>
<p class="muted">Every code pulled from Notion for this pod, and whether any contractor has claimed it yet ({claimed_count} of {len(notion_codes)} claimed).</p>
<table>
<thead><tr><th>Code</th><th>Status</th><th>Detail</th></tr></thead>
<tbody>
{rows_html}
</tbody>
</table>
"""


def _period_line(reconciliation):
    periods = sorted(
        {(c.date_from, c.date_to) for c in reconciliation.hours_checks}
        | {(c.date_from, c.date_to) for c in reconciliation.code_checks}
    )
    if not periods:
        return ""
    if len(periods) == 1:
        date_from, date_to = periods[0]
        return f'<p class="period-line">Period: {escape(date_from)} &rarr; {escape(date_to)}</p>'
    # More than one period in this run (e.g. a CSV covering several weeks) —
    # list them all rather than assume a single one.
    joined = "; ".join(f"{escape(a)} &rarr; {escape(b)}" for a, b in periods)
    return f'<p class="period-line">Periods: {joined}</p>'


def render_pod_tables(reconciliation):
    """Returns an HTML fragment (no page shell) with this one pod's two
    reconciliation tables, for embedding on that pod's own page."""
    hours_mismatches = sum(1 for c in reconciliation.hours_checks if c.status == "mismatch")
    code_mismatches = sum(1 for c in reconciliation.code_checks if c.status == "mismatch")
    period_line = _period_line(reconciliation)

    hours_rows = "\n".join(
        f"""<tr>
  <td>{escape(c.contractor)}</td>
  <td>{c.submitted_minutes:.0f}m</td>
  <td>{c.expected_minutes:.0f}m</td>
  <td>{_status_span(c.status)}</td>
  <td class="muted">{escape(c.detail)}</td>
</tr>"""
        for c in sorted(reconciliation.hours_checks, key=lambda c: (c.contractor, c.date_from))
    ) or '<tr><td colspan="5" class="muted">No submissions yet.</td></tr>'

    code_rows = "\n".join(
        f"""<tr>
  <td>{escape(c.contractor)}</td>
  <td>{escape(c.code)}<br><span class="muted">{escape(c.label) if c.label else '(unrecognized prefix)'}</span></td>
  <td>{_status_span(c.status)}</td>
  <td class="muted">{escape(c.detail)}</td>
</tr>"""
        for c in sorted(reconciliation.code_checks, key=lambda c: (c.contractor, c.date_from, c.code))
    ) or '<tr><td colspan="4" class="muted">No submissions yet.</td></tr>'

    return f"""
<p class="muted">{hours_mismatches} hours mismatch(es), {code_mismatches} code mismatch(es).</p>

<h2>Submitted time vs. code stamps</h2>
<p class="muted">Does each submission's total time match what its logged codes add up to?</p>
{period_line}
<table>
<thead><tr><th>Contractor</th><th>Submitted</th><th>Expected</th><th>Status</th><th>Detail</th></tr></thead>
<tbody>
{hours_rows}
</tbody>
</table>

<h2>Upwork codes vs. Notion master list</h2>
<p class="muted">Does each submitted code exactly match one on Notion's master list, and hasn't this contractor already claimed it in a previous run?</p>
{period_line}
<table>
<thead><tr><th>Contractor</th><th>Code</th><th>Status</th><th>Detail</th></tr></thead>
<tbody>
{code_rows}
</tbody>
</table>
"""
