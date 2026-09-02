"""Two kinds of page, both password-gated: a landing page (pod navigation +
the GitHub token, which is shared across pods via localStorage) and one
page per pod (CSV drop zone, unassigned-handle assignment, Run Report
button, and that pod's own reconciliation tables).

Deliberately NOT real security: the password gate is a client-side SHA-256
comparison (trivially bypassable via view-source), and the pages' only real
protection is (a) Netlify's own site-wide password, and (b) a GitHub token
scoped to just this one repo's Contents/Actions APIs, entered once (on the
landing page) and kept in the browser's localStorage only — shared across
every pod page on this site since localStorage is per-origin, never written
to the repo or bundled into the deployed source. Same mechanism as the
Weekly/Monthly dashboards' Admin pages, same password by choice.

Assignment writes go straight to pod_data/{slug}.json in this repo via the
GitHub Contents API (GET for the current sha, then PUT the updated JSON) —
see config.py's _load_pod_overlay()/load_pods() for how the pipeline reads
it back. Assigning someone to a pod slug that doesn't exist in pods.yaml
yet creates that pod entirely from pod_data (no brands until those are
added by hand — this only manages contractor-to-pod-and-role assignment).
"""

import json
from html import escape

from .render import TABLE_CSS, render_pod_tables

GITHUB_OWNER = "emailpunks"
GITHUB_REPO = "upwork"
REPORT_WORKFLOW = "pod-report.yml"

# SHA-256 hex digest of the page password. Same password as the
# Weekly/Monthly dashboards' Admin pages, by choice — see those repos'
# admin_page.py for how to change it (same mechanism, not real security
# either way).
PASSWORD_SHA256 = "08fcf9917fe0f61ff5cab6e52d8bf058119f3497d9c21c856911d403a29084d9"


def _page_shell(title, app_body, script):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="robots" content="noindex, nofollow" />
<style>{CSS}</style>
</head>
<body>

<div id="gate" class="wrap gate">
  <h1>{title}</h1>
  <p class="muted">Internal use only.</p>
  <input type="password" id="gate-password" placeholder="Password" autocomplete="off" />
  <button id="gate-submit" class="btn btn-primary">Enter</button>
  <p id="gate-error" class="error" style="display:none">Wrong password.</p>
</div>

<div id="app" class="wrap" style="display:none">
{app_body}
</div>

<script>
{GATE_JS.format(password_hash=PASSWORD_SHA256)}
{script}
</script>
</body>
</html>"""


def render_index_page(all_pods):
    """Landing page: GitHub token (shared across every pod page via
    localStorage) + links to each pod's own page."""
    pod_links = "\n".join(
        f'<a href="{escape(p.slug)}/">{escape(p.name)}</a>' for p in all_pods
    ) or '<p class="muted">No pods yet.</p>'

    app_body = f"""
<h1>Pod Reconciliation</h1>
<p class="muted">Upwork time submissions checked against Notion task records, by pod.</p>

<section class="card">
  <h2>GitHub access</h2>
  <p class="muted">A token is required to save contractor assignments or run a new report from a pod's page — entered once here, kept only in this browser (never sent anywhere but GitHub, never written to the repo), shared across every pod page on this site.</p>
  <details id="token-help">
    <summary>How do I get a token?</summary>
    <ol>
      <li>Go to <a href="https://github.com/settings/tokens/new" target="_blank" rel="noopener">github.com/settings/tokens/new</a> (classic token)</li>
      <li>Give it a note (e.g. "pod dashboard") and an expiration</li>
      <li>Under <strong>Select scopes</strong>, check <strong>repo</strong> (Full control of private repositories) and <strong>workflow</strong> — covers both saving assignments and the Run Report button on each pod's page</li>
      <li>Generate the token and paste it below</li>
    </ol>
  </details>
  <div class="row">
    <input type="password" id="gh-token" placeholder="ghp_..." autocomplete="off" />
    <button id="gh-token-save" class="btn">Save token</button>
    <button id="gh-token-clear" class="btn btn-ghost">Clear</button>
  </div>
  <p id="gh-token-status" class="muted"></p>
</section>

<div class="card pod-list">
{pod_links}
</div>
"""
    return _page_shell("Pod Reconciliation", app_body, TOKEN_JS)


def render_pod_page(pod, reconciliation, all_pods, roles, unknown_handles=None):
    tables_html = render_pod_tables(reconciliation)

    unknown_warning = ""
    if unknown_handles:
        handles = ", ".join(escape(h) for h in unknown_handles)
        unknown_warning = (
            f'<div class="warning">Upwork submissions from handle(s) not found in any pod\'s roster '
            f"(from the last report run): {handles}</div>"
        )

    pods_json = json.dumps([{"slug": p.slug, "name": p.name} for p in all_pods])
    handles_json = json.dumps(sorted({c.upwork_handle for p in all_pods for c in p.contractors}))
    roles_json = json.dumps(sorted(roles.keys()))

    app_body = f"""
<p class="muted"><a href="../">&larr; All pods</a></p>
<h1>{escape(pod.name)}</h1>
{unknown_warning}

<section class="card">
  <h2>Timesheet CSV</h2>
  <p class="muted">Drop the CSV exported from Upwork's client timesheet report, or click to choose the file.</p>
  <div id="drop-zone" class="drop-zone">
    <span id="drop-zone-text">Drop CSV here, or click to choose a file</span>
    <input type="file" id="csv-file-input" accept=".csv,text/csv" style="display:none" />
  </div>
  <details style="margin-top:10px;">
    <summary>Paste text instead</summary>
    <textarea id="csv-input" rows="8" placeholder='"Date from","Date to","Talent","Hours","Memo"&#10;...' style="margin-top:8px;"></textarea>
  </details>
  <div class="row" style="margin-top:10px;">
    <button id="parse-btn" class="btn btn-primary">Parse CSV</button>
  </div>
  <p id="parse-status" class="muted"></p>
</section>

<section class="card" id="unassigned-card" style="display:none">
  <h2>Unassigned handles</h2>
  <p class="muted">Found in the CSV but not assigned to any pod yet. Pick a pod and role for each, then save.</p>
  <div class="row" style="margin-bottom: 10px;">
    <label style="width:auto;">New pod name</label>
    <input type="text" id="new-pod-name" placeholder="e.g. P2" style="max-width:160px;" />
    <button id="add-pod-btn" class="btn btn-ghost" type="button">Add to pod list</button>
  </div>
  <table id="unassigned-table">
    <thead><tr><th>Name</th><th>Handle</th><th>Pod</th><th>Role</th></tr></thead>
    <tbody id="unassigned-body"></tbody>
  </table>
  <div class="row" style="margin-top:14px;">
    <button id="save-assignments-btn" class="btn btn-primary">Save Assignments</button>
  </div>
  <p id="save-status" class="muted"></p>
</section>

<section class="card">
  <h2>Run Report</h2>
  <p class="muted">Runs the reconciliation pipeline with the CSV above and rebuilds every pod's page. Takes a few minutes.</p>
  <button id="run-report-btn" class="btn">Run Report</button>
  <p id="run-status" class="muted" style="margin-top:8px;"></p>
</section>

{tables_html}
"""
    script = ADMIN_JS.format(
        admin_owner=GITHUB_OWNER,
        admin_repo=GITHUB_REPO,
        pods_json=pods_json,
        handles_json=handles_json,
        roles_json=roles_json,
        report_workflow=REPORT_WORKFLOW,
        default_pod_slug=pod.slug,
    )
    return _page_shell(escape(pod.name), app_body, script)


CSS = (
    """
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
.gate { max-width: 320px; padding-top: 120px; text-align: center; }
h1 { font-size: 22px; margin: 0 0 8px; }
h2 { font-size: 16px; margin: 0 0 6px; }
.muted { color: var(--text-muted); font-size: 12.5px; line-height: 1.5; }
a { color: var(--accent); }
.error { color: var(--bad); font-size: 12.5px; }
.card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 20px;
  margin-bottom: 20px;
}
.pod-list a { display: block; padding: 10px 0; border-bottom: 1px solid var(--border); }
.pod-list a:last-child { border-bottom: none; }
input[type="text"], input[type="password"], select, textarea {
  border: 1px solid var(--border);
  background: var(--page);
  color: var(--text-primary);
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 13px;
  width: 100%;
  font-family: inherit;
}
textarea { font-family: ui-monospace, monospace; font-size: 12px; resize: vertical; }
.row { display: flex; align-items: center; gap: 8px; margin: 10px 0; }
.row label { width: 140px; flex-shrink: 0; font-size: 12.5px; color: var(--text-secondary); }
.btn {
  border: 1px solid var(--border);
  background: var(--surface-1);
  color: var(--text-primary);
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.btn-primary { background: var(--accent); color: #2b2b2b; border-color: var(--accent); font-weight: 600; }
.btn-ghost { background: none; }
.gate input { width: 100%; margin: 16px 0 10px; }
.gate .btn { width: 100%; }
details { margin: 10px 0; font-size: 12.5px; }
summary { cursor: pointer; color: var(--accent); }
details ol { color: var(--text-secondary); padding-left: 20px; }
details a { color: var(--accent); }
.ok { color: var(--good); }
td select { min-width: 130px; }
.drop-zone {
  border: 2px dashed var(--border);
  border-radius: 10px;
  padding: 28px 16px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
}
.drop-zone.drag-over { border-color: var(--accent); color: var(--text-primary); background: rgba(249,188,60,0.06); }
.warning { background: rgba(249,188,60,0.12); border: 1px solid rgba(249,188,60,0.3); border-radius: 8px; padding: 10px 14px; font-size: 12.5px; color: var(--warn); margin: 16px 0; }
"""
    + TABLE_CSS
)


# Password gate + "remembered unlock" (localStorage flag) so navigating
# between the landing page and pod pages doesn't re-prompt every time.
# Shared by both page templates.
GATE_JS = """
  var PASSWORD_HASH = "{password_hash}";

  function sha256Hex(text) {{
    var data = new TextEncoder().encode(text);
    return crypto.subtle.digest('SHA-256', data).then(function(buf) {{
      return Array.prototype.map.call(new Uint8Array(buf), function(b) {{
        return b.toString(16).padStart(2, '0');
      }}).join('');
    }});
  }}

  function unlock() {{
    document.getElementById('gate').style.display = 'none';
    document.getElementById('app').style.display = '';
  }}

  if (localStorage.getItem('pod_dashboard_unlocked') === '1') {{ unlock(); }}

  document.getElementById('gate-submit').addEventListener('click', checkPassword);
  document.getElementById('gate-password').addEventListener('keydown', function(e) {{
    if (e.key === 'Enter') checkPassword();
  }});

  function checkPassword() {{
    var val = document.getElementById('gate-password').value;
    sha256Hex(val).then(function(hash) {{
      if (hash === PASSWORD_HASH) {{
        localStorage.setItem('pod_dashboard_unlocked', '1');
        unlock();
      }} else {{
        document.getElementById('gate-error').style.display = '';
      }}
    }});
  }}

  function getToken() {{ return localStorage.getItem('admin_gh_token') || ''; }}
"""


# Landing-page-only: the token input's save/clear/status UI. Reading the
# token (getToken) is defined in GATE_JS since pod pages need it too.
TOKEN_JS = """
  var tokenInput = document.getElementById('gh-token');
  var tokenStatus = document.getElementById('gh-token-status');
  function refreshTokenStatus() {
    tokenStatus.textContent = getToken() ? 'Token saved in this browser.' : 'No token saved yet.';
  }
  refreshTokenStatus();

  document.getElementById('gh-token-save').addEventListener('click', function() {
    if (tokenInput.value.trim()) {
      localStorage.setItem('admin_gh_token', tokenInput.value.trim());
      tokenInput.value = '';
      refreshTokenStatus();
    }
  });
  document.getElementById('gh-token-clear').addEventListener('click', function() {
    localStorage.removeItem('admin_gh_token');
    refreshTokenStatus();
  });
"""


# Pod-page-only: CSV drop/parse, unassigned-handle assignment, Run Report.
ADMIN_JS = """
  var OWNER = "{admin_owner}";
  var REPO = "{admin_repo}";
  var PODS = {pods_json};
  var KNOWN_HANDLES = {handles_json};
  var ROLE_NAMES = {roles_json};
  var REPORT_WORKFLOW = "{report_workflow}";
  var DEFAULT_POD_SLUG = "{default_pod_slug}";

  function b64EncodeUtf8(str) {{
    return btoa(unescape(encodeURIComponent(str)));
  }}
  function b64DecodeUtf8(b64) {{
    return decodeURIComponent(escape(atob(b64)));
  }}

  function ghRequest(method, path, body) {{
    var headers = {{
      'Authorization': 'Bearer ' + getToken(),
      'Accept': 'application/vnd.github+json',
    }};
    var opts = {{ method: method, headers: headers }};
    if (body !== undefined) {{ opts.body = JSON.stringify(body); }}
    return fetch('https://api.github.com/repos/' + OWNER + '/' + REPO + '/' + path, opts);
  }}

  // ---- CSV parsing (RFC4180-ish: handles quoted fields with embedded
  // commas/newlines and doubled-quote escaping, since the Memo column has
  // both) ----
  function parseCSV(text) {{
    var rows = [];
    var row = [];
    var field = '';
    var inQuotes = false;
    for (var i = 0; i < text.length; i++) {{
      var c = text[i];
      if (inQuotes) {{
        if (c === '"') {{
          if (text[i + 1] === '"') {{ field += '"'; i++; }}
          else {{ inQuotes = false; }}
        }} else {{
          field += c;
        }}
      }} else {{
        if (c === '"') {{ inQuotes = true; }}
        else if (c === ',') {{ row.push(field); field = ''; }}
        else if (c === '\\r') {{ /* skip */ }}
        else if (c === '\\n') {{ row.push(field); rows.push(row); row = []; field = ''; }}
        else {{ field += c; }}
      }}
    }}
    if (field.length || row.length) {{ row.push(field); rows.push(row); }}
    return rows;
  }}

  function extractHandle(talent) {{
    var m = talent.match(/\\(([^)]+)\\)\\s*$/);
    return m ? m[1] : talent;
  }}

  var unassigned = []; // [{{name, handle}}]

  // ---- Drop zone / file picker for the CSV ----
  var dropZone = document.getElementById('drop-zone');
  var dropZoneText = document.getElementById('drop-zone-text');
  var fileInput = document.getElementById('csv-file-input');

  function loadCsvFile(file) {{
    if (!file) return;
    dropZoneText.textContent = 'Reading ' + file.name + '…';
    var reader = new FileReader();
    reader.onload = function() {{
      document.getElementById('csv-input').value = reader.result;
      dropZoneText.textContent = 'Loaded ' + file.name + ' — click Parse CSV below';
      document.getElementById('parse-btn').click();
    }};
    reader.onerror = function() {{
      dropZoneText.textContent = 'Could not read that file — try again.';
    }};
    reader.readAsText(file);
  }}

  dropZone.addEventListener('click', function() {{ fileInput.click(); }});
  fileInput.addEventListener('change', function() {{ loadCsvFile(fileInput.files[0]); }});

  ['dragenter', 'dragover'].forEach(function(evt) {{
    dropZone.addEventListener(evt, function(e) {{
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('drag-over');
    }});
  }});
  ['dragleave', 'drop'].forEach(function(evt) {{
    dropZone.addEventListener(evt, function(e) {{
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('drag-over');
    }});
  }});
  dropZone.addEventListener('drop', function(e) {{
    var file = e.dataTransfer.files && e.dataTransfer.files[0];
    loadCsvFile(file);
  }});

  document.getElementById('parse-btn').addEventListener('click', function() {{
    var status = document.getElementById('parse-status');
    var text = document.getElementById('csv-input').value;
    if (!text.trim()) {{ status.textContent = 'Paste a CSV first.'; return; }}

    var rows = parseCSV(text);
    if (rows.length < 2) {{ status.textContent = 'Could not find any data rows.'; return; }}

    var header = rows[0];
    var talentIdx = header.indexOf('Talent');
    if (talentIdx === -1) {{ status.textContent = 'No "Talent" column found — is this the right CSV?'; return; }}

    var seen = {{}};
    var uniqueTalents = [];
    for (var i = 1; i < rows.length; i++) {{
      var talent = (rows[i][talentIdx] || '').trim();
      if (!talent) continue;
      var handle = extractHandle(talent);
      if (seen[handle]) continue;
      seen[handle] = true;
      var name = talent.replace(/\\s*\\([^)]*\\)\\s*$/, '').trim();
      uniqueTalents.push({{ name: name, handle: handle }});
    }}

    unassigned = uniqueTalents.filter(function(t) {{ return KNOWN_HANDLES.indexOf(t.handle) === -1; }});
    status.textContent = uniqueTalents.length + ' handle(s) found in CSV, ' + unassigned.length + ' unassigned.';
    renderUnassignedTable();
  }});

  function podOptionsHtml() {{
    return PODS.map(function(p) {{
      var selected = p.slug === DEFAULT_POD_SLUG ? ' selected' : '';
      return '<option value="' + p.slug + '"' + selected + '>' + p.name + '</option>';
    }}).join('');
  }}
  function roleOptionsHtml() {{
    return '<option value=""></option>' + ROLE_NAMES.map(function(r) {{
      return '<option value="' + r + '">' + r + '</option>';
    }}).join('');
  }}

  function renderUnassignedTable() {{
    var card = document.getElementById('unassigned-card');
    var body = document.getElementById('unassigned-body');
    body.innerHTML = '';

    if (unassigned.length === 0) {{
      card.style.display = 'none';
      return;
    }}
    card.style.display = '';

    unassigned.forEach(function(t, idx) {{
      var tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + t.name + '</td>' +
        '<td>' + t.handle + '</td>' +
        '<td><select data-idx="' + idx + '" class="pod-select"><option value="">Choose&hellip;</option>' + podOptionsHtml() + '</select></td>' +
        '<td><select data-idx="' + idx + '" class="role-select">' + roleOptionsHtml() + '</select></td>';
      body.appendChild(tr);
    }});
  }}

  document.getElementById('add-pod-btn').addEventListener('click', function() {{
    var input = document.getElementById('new-pod-name');
    var name = input.value.trim();
    if (!name) return;
    var slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    if (!slug) return;
    if (PODS.some(function(p) {{ return p.slug === slug; }})) {{
      input.value = '';
      return;
    }}
    PODS.push({{ slug: slug, name: name }});
    input.value = '';
    renderUnassignedTable();
  }});

  document.getElementById('save-assignments-btn').addEventListener('click', function() {{
    var status = document.getElementById('save-status');
    if (!getToken()) {{ status.innerHTML = '<span class="error">Set a GitHub token on the main page first.</span>'; return; }}

    var podSelects = document.querySelectorAll('.pod-select');
    var byPod = {{}}; // slug -> [{{name, upwork_handle, role}}]
    var assignedIdx = [];

    podSelects.forEach(function(sel) {{
      var idx = parseInt(sel.getAttribute('data-idx'), 10);
      var podSlug = sel.value;
      var roleSel = document.querySelector('.role-select[data-idx="' + idx + '"]');
      var role = roleSel ? roleSel.value : '';
      if (!podSlug || !role) return;
      var t = unassigned[idx];
      if (!byPod[podSlug]) byPod[podSlug] = [];
      byPod[podSlug].push({{ name: t.name, upwork_handle: t.handle, role: role }});
      assignedIdx.push(idx);
    }});

    var podSlugs = Object.keys(byPod);
    if (podSlugs.length === 0) {{
      status.textContent = 'Pick a pod and role for at least one row first.';
      return;
    }}

    status.textContent = 'Saving...';

    function saveOnePod(slug) {{
      var podMeta = PODS.filter(function(p) {{ return p.slug === slug; }})[0];
      return ghRequest('GET', 'contents/pod_data/' + slug + '.json').then(function(resp) {{
        if (resp.status === 404) {{
          return {{ data: {{ name: (podMeta ? podMeta.name : slug), contractors: [] }}, sha: null }};
        }}
        if (!resp.ok) return resp.text().then(function(t) {{ throw new Error('GitHub GET failed (' + resp.status + '): ' + t); }});
        return resp.json().then(function(json) {{
          var data = JSON.parse(b64DecodeUtf8(json.content.replace(/\\n/g, '')));
          if (!data.contractors) data.contractors = [];
          return {{ data: data, sha: json.sha }};
        }});
      }}).then(function(current) {{
        var existingHandles = current.data.contractors.map(function(c) {{ return c.upwork_handle; }});
        byPod[slug].forEach(function(c) {{
          if (existingHandles.indexOf(c.upwork_handle) === -1) {{
            current.data.contractors.push(c);
            existingHandles.push(c.upwork_handle);
          }}
        }});
        var body = {{
          message: 'Assign contractor(s) to pod ' + slug + ' via the pod page',
          content: b64EncodeUtf8(JSON.stringify(current.data, null, 2)),
        }};
        if (current.sha) body.sha = current.sha;
        return ghRequest('PUT', 'contents/pod_data/' + slug + '.json', body).then(function(resp) {{
          return resp.json().then(function(json) {{
            if (!resp.ok) throw new Error(json.message || ('GitHub PUT failed (' + resp.status + ')'));
          }});
        }});
      }});
    }}

    Promise.all(podSlugs.map(saveOnePod)).then(function() {{
      assignedIdx.forEach(function(idx) {{ KNOWN_HANDLES.push(unassigned[idx].handle); }});
      unassigned = unassigned.filter(function(t, idx) {{ return assignedIdx.indexOf(idx) === -1; }});
      renderUnassignedTable();
      status.innerHTML = '<span class="ok">Saved. Takes effect on the next report run.</span>';
    }}).catch(function(err) {{
      status.innerHTML = '<span class="error">Error: ' + err.message + '</span>';
    }});
  }});

  // ---- Run Report ----
  function latestRun() {{
    return ghRequest('GET', 'actions/workflows/' + REPORT_WORKFLOW + '/runs?per_page=1')
      .then(function(resp) {{ return resp.ok ? resp.json() : null; }})
      .then(function(json) {{ return json && json.workflow_runs && json.workflow_runs[0]; }});
  }}
  function isBusy(run) {{ return run && run.status !== 'completed'; }}

  var runStartTime = null;
  var runElapsedTimer = null;
  var runLastStatusText = '';
  var pendingTriggerAt = null;

  function formatElapsed(ms) {{
    var totalSec = Math.max(0, Math.floor(ms / 1000));
    var m = Math.floor(totalSec / 60);
    var s = totalSec % 60;
    return m + 'm ' + (s < 10 ? '0' : '') + s + 's';
  }}
  function stopElapsedTimer() {{
    if (runElapsedTimer) {{ clearInterval(runElapsedTimer); runElapsedTimer = null; }}
    runStartTime = null;
  }}
  function updateElapsedDisplay() {{
    if (!runStartTime) return;
    document.getElementById('run-status').textContent =
      (runLastStatusText || 'Running…') + ' (' + formatElapsed(Date.now() - runStartTime) + ' elapsed)';
  }}
  function startElapsedTimer(startTimeMs) {{
    stopElapsedTimer();
    runStartTime = startTimeMs || Date.now();
    updateElapsedDisplay();
    runElapsedTimer = setInterval(updateElapsedDisplay, 1000);
  }}

  function pollRunStatus() {{
    var btn = document.getElementById('run-report-btn');
    latestRun().then(function(run) {{
      if (pendingTriggerAt && (!run || new Date(run.created_at).getTime() < pendingTriggerAt - 30000)) {{
        runLastStatusText = 'Triggered — waiting for it to appear…';
        updateElapsedDisplay();
        setTimeout(pollRunStatus, 5000);
        return;
      }}
      if (!run || run.status === 'completed') {{
        stopElapsedTimer();
        var statusEl = document.getElementById('run-status');
        if (run && run.status === 'completed') {{
          statusEl.textContent = run.conclusion === 'success'
            ? 'Done — reload the page to see the latest data.'
            : 'Run finished with status: ' + run.conclusion;
        }}
        pendingTriggerAt = null;
        btn.disabled = false;
        return;
      }}
      runLastStatusText = 'Running… (' + run.status + ') — this can take a few minutes.';
      updateElapsedDisplay();
      setTimeout(pollRunStatus, 15000);
    }}).catch(function() {{
      stopElapsedTimer();
      btn.disabled = false;
    }});
  }}

  document.getElementById('run-report-btn').addEventListener('click', function() {{
    var btn = this;
    var statusEl = document.getElementById('run-status');
    btn.disabled = true;
    if (!getToken()) {{ statusEl.textContent = 'Set a GitHub token on the main page first.'; btn.disabled = false; return; }}
    var csv = document.getElementById('csv-input').value;
    if (!csv.trim()) {{ statusEl.textContent = 'Drop or paste a CSV above first.'; btn.disabled = false; return; }}

    latestRun().then(function(run) {{
      if (isBusy(run)) {{
        runLastStatusText = 'A report run is already in progress — wait for it to finish.';
        startElapsedTimer(run.created_at ? new Date(run.created_at).getTime() : null);
        setTimeout(pollRunStatus, 15000);
        return;
      }}
      if (!confirm('Run the reconciliation report now with this CSV? Rebuilds every pod\\'s page.')) {{
        statusEl.textContent = '';
        btn.disabled = false;
        return;
      }}
      statusEl.textContent = 'Triggering…';
      ghRequest('POST', 'actions/workflows/' + REPORT_WORKFLOW + '/dispatches', {{
        ref: 'main',
        inputs: {{ csv_content: csv }},
      }}).then(function(resp) {{
        if (resp.status !== 204) {{
          return resp.text().then(function(t) {{ throw new Error(t || ('Failed (' + resp.status + ')')); }});
        }}
        pendingTriggerAt = Date.now();
        runLastStatusText = 'Triggered — waiting for it to start…';
        startElapsedTimer(pendingTriggerAt);
        setTimeout(pollRunStatus, 5000);
      }}).catch(function(err) {{
        statusEl.textContent = 'Error: ' + err.message;
        btn.disabled = false;
      }});
    }}).catch(function(err) {{
      statusEl.textContent = 'Could not check run status: ' + err.message;
      btn.disabled = false;
    }});
  }});

  if (getToken()) {{
    latestRun().then(function(run) {{
      if (isBusy(run)) {{
        document.getElementById('run-report-btn').disabled = true;
        runLastStatusText = 'A report run is already in progress (' + run.status + ').';
        startElapsedTimer(run.created_at ? new Date(run.created_at).getTime() : null);
        setTimeout(pollRunStatus, 15000);
      }}
    }}).catch(function() {{}});
  }}
"""
