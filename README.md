# Pod Reconciliation Dashboard

Checks contractor time submitted on Upwork against the matching task records
in Notion, split by pod. Each contractor has a role, and each role has a set
of two-letter task codes with a fixed expected duration (e.g. `ES` = 60
min). Two independent checks run per pod:

1. **Submitted time vs. code stamps** — does the total time a contractor
   submitted on Upwork match what their logged codes add up to (using each
   code's fixed duration)?
2. **Upwork codes vs. Notion records** — does the number of times each code
   was submitted on Upwork match how many times Notion shows that code's
   task actually completed?

Static-site pipeline: `main.py` parses an exported Upwork timesheet CSV,
pulls from Notion, reconciles, and writes `output/<pod-slug>/index.html`,
deployed to Netlify via GitHub Actions (same shape as the
`weekly-reports`/`monthly-reports` dashboards).

## Why CSV, not the Upwork API

Upwork's timesheet data lives behind their GraphQL API, but every new API
app is manually reviewed by Upwork before it works — no guaranteed
turnaround, reportedly around a week. Rather than block on that, this
pulls from a CSV exported straight from Upwork's client timesheet report
(`nx/reports/client/timesheet/` → Export). If Upwork ever approves faster
API access, swapping the CSV parser (`pod_dashboard/upwork_csv.py`) for a
live API client wouldn't touch anything downstream (reconciliation,
rendering) — see the git history for the GraphQL version this replaced.

## The CSV memo format

Each CSV row is one contractor's submission for a week: `Date from`,
`Date to`, `Talent` (`"Name (upwork_handle)"`), `Hours`, and `Memo` — a
list of task stamps like `CT11626081516482608231519`, separated by
newlines or spaces. **Only the first two letters of each stamp matter** —
everything after that (task ID, timestamps) is internal to how Notion
generates the stamp and isn't parsed. See `pod_dashboard/upwork_csv.py`.

## Setup

### 1. Notion

1. Create an internal integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
   — this gives you a secret token, no code required.
2. For each Notion database referenced in `pods.yaml`, open it, click
   "..." → **Connections**, and add this integration. Without this step the
   API can't see the database at all, even with a valid token.

### 2. Fill in secrets

Copy `pods.secrets.yaml.example` to `pods.secrets.yaml` (gitignored) and
fill in the Notion token. For CI, set the same value as a `NOTION_TOKEN`
GitHub Actions secret.

### 3. Fill in `pods.yaml`

Roles and task codes are already filled in (shared across every pod — see
the top of the file). Pods are named P1, P2, etc.; brands (which Notion
database each pod's tasks live in) need to be added by hand once known.
**Contractors don't** — see Admin page below. Note
`contractors[].upwork_handle` — that's the short handle Upwork shows in
parentheses after a contractor's name (e.g. `Jane Doe (abc12de)`), not
their display name.

### 4. Netlify

Create a Netlify site for this repo (same as Weekly/Monthly) and add
`NETLIFY_AUTH_TOKEN`/`NETLIFY_SITE_ID` as GitHub Actions secrets.

## Running

Export the timesheet CSV from Upwork (`nx/reports/client/timesheet/` →
Export), then:

```bash
pip install -r requirements.txt
python3 main.py path/to/export.csv       # all pods
python3 main.py path/to/export.csv p1    # just one pod, by slug
```

To check the reconciliation + rendering logic without a real CSV or Notion
credentials:

```bash
python3 scripts/demo.py    # writes output/ from fixtures/
```

### Running from GitHub, without a terminal

The `Pod reconciliation report` workflow (Actions tab → "Run workflow")
takes the full CSV contents pasted into a text box, so a routine run
doesn't need a local checkout — export the CSV, open it in a text editor,
paste the contents in, run. The Admin page below does this same thing
without needing the Actions tab at all.

## Admin page

Every pod page's footer has a small "Admin" link. That page lets you:

- **Paste a timesheet CSV and see unassigned handles.** Any Upwork handle
  in the CSV that isn't yet assigned to a contractor in any pod shows up
  with a Pod + Role picker — pick both and save, no YAML editing. New pods
  can be created inline (type a name like "P2", click "Add to pod list") —
  a pod created this way has no brands until those are added to `pods.yaml`
  by hand.
- **Run the report** with that same pasted CSV, redeploying every pod's
  page — the same trigger as the GitHub Actions "Run workflow" button, just
  without leaving the page.

Assignments are written to `pod_data/{slug}.json` (one file per pod,
merged with `pods.yaml` at build time — see `pod_dashboard/config.py`).
It's gated by a password (same one as Weekly/Monthly's Admin pages — not
real security, just a speed bump) and a GitHub personal access token you
generate yourself and keep only in your browser's local storage, scoped to
this repo's Contents + Actions APIs. See the page itself for how to
generate one.
