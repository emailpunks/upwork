# Pod Reconciliation Dashboard

Checks contractor time submitted on Upwork against the matching task records
in Notion, split by pod. Each contractor has a role, and each role has a set
of two-letter task codes with a fixed expected duration (e.g. `ES` = 60
min). Two independent checks run per pod:

1. **Submitted time vs. code stamps** — does the total time a contractor
   submitted on Upwork match what their logged codes add up to (using each
   code's two-letter prefix and its fixed duration)?
2. **Upwork codes vs. Notion master list** — does each *full* code a
   contractor submitted exactly match one on Notion's master list (pulled
   fresh every run), and hasn't this same contractor already claimed it in
   a previous run? Notion has no per-contractor assignment — a code is
   just a ticket, and any pod member can legitimately submit it once each.
   Notion is read-only here — nothing is ever written back to it. Instead,
   every code confirmed as a genuine, first-time-for-this-contractor match
   gets recorded in `used_codes/{pod-slug}.json` (see
   `pod_dashboard/ledger.py`), committed back to this repo by the GitHub
   Actions workflow after each run, so that contractor can't re-claim it
   later (someone else on the pod still can, once).

Static-site pipeline: `main.py` parses an exported Upwork timesheet CSV,
pulls from Notion, reconciles, and writes a landing page
(`output/index.html`) plus one page per pod (`output/<slug>/index.html`),
every page behind its own password gate — see "The pages" below — deployed
to Netlify via GitHub Actions (same shape as the
`weekly-reports`/`monthly-reports` dashboards otherwise).

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
list of task stamps, separated by newlines or spaces. Two stamp shapes
show up: `CT11626081516482608231519` (legacy — all digits after the
prefix) and `HE12608171600VENB` (current — a 4-letter brand suffix after
the digits, which is also how a code's creation date gets derived back
out — see `notion_client.py`'s `code_created_date`). The **whole stamp**
is kept either way (not just the two-letter prefix): the prefix alone
drives the hours check (its fixed duration from `pods.yaml`), but the
full stamp is what gets checked for an exact match against Notion's
master list. See `pod_dashboard/upwork_csv.py`.

## Setup

### 1. Notion

1. Create an internal integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
   — this gives you a secret token, no code required.
2. For each Notion database referenced in `pods.yaml`, open it, click
   "..." → **Connections**, and add this integration. Without this step the
   API can't see the database at all, even with a valid token.
3. That database's "Task Code" property (whatever it's called — see
   `notion_property_map` in `pods.yaml`) needs to hold the **full**
   generated code (e.g. `TB11426081516482608251636`), not just the
   two-letter prefix — that's what gets checked against Upwork.

### 2. Fill in secrets

Copy `pods.secrets.yaml.example` to `pods.secrets.yaml` (gitignored) and
fill in the Notion token. For CI, set the same value as a `NOTION_TOKEN`
GitHub Actions secret.

### 3. Fill in `pods.yaml`

Roles and task codes are already filled in (shared across every pod — see
the top of the file). Pods are named P1, P2, etc. **Neither brands nor
contractors need to be added here by hand** — see "The pages" below. Note
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
paste the contents in, run. Once the site's live, "The pages" below does
this same thing (drag-and-drop, not paste) without needing the Actions
tab at all — the GitHub Actions route only matters for the very first
deploy, before any page exists yet.

## The pages

Every page (`pod_dashboard/page.py`) is behind the same password gate —
no separate public dashboard and no separate hidden admin URL. Entering
the password on any page unlocks every other page too (remembered in the
browser), so it's only asked once per browser.

- **Landing page** (`/`): lists every pod, and holds the GitHub personal
  access token — entered once here, kept in the browser's local storage,
  shared across every pod page on the site since it's the same origin.
- **Each pod's own page** (`/<slug>/`):
  - **Brands** — add a brand by name plus one or more Notion database IDs
    (one per line); adding the same brand name again appends new IDs to
    it rather than replacing it. No YAML editing required, though the
    Notion integration still needs to be shared with each database first
    (see Setup above).
  - **Timesheet CSV** — drop a file to see handles in it that aren't
    assigned to a contractor in any pod yet, each with a Pod + Role
    picker (defaulting to the current pod). New pods can be created
    inline too (type a name like "P2", click "Add to pod list") — a pod
    created this way starts with no brands until added here.
  - **Run Report** — re-runs the whole pipeline with that CSV and
    rebuilds every pod's page, same trigger as the GitHub Actions "Run
    workflow" button, without leaving the page.
  - **Cutoff date** — codes created before this date are dropped entirely,
    right after the Notion pull, and never come back on future runs.
    Creation date is derived from the code itself (see
    `notion_client.py`'s `code_created_date`), not stored separately.
  - Then that pod's own reconciliation tables, and a collapsible **Notion
    master list** — every code pulled from Notion (after the cutoff),
    its derived creation date, and whether it's been claimed.

Assignments are written to `pod_data/{slug}.json` (one file per pod,
merged with `pods.yaml` at build time — see `pod_dashboard/config.py`).
The password is the same one as Weekly/Monthly's Admin pages (not real
security, just a speed bump). See the landing page for how to generate the
GitHub token.
