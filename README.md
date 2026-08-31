# Pod Reconciliation Dashboard

Checks contractor time submitted on Upwork against the matching task records
in Notion, split by pod. Each contractor has a role, and each role has a set
of two-letter task codes with an expected duration (e.g. `ES` = 60 min). A
mismatch — wrong code, wrong duration, or missing on one side — shows up on
that pod's page.

Static-site pipeline: `main.py` pulls from Upwork + Notion, reconciles, and
writes `output/<pod-slug>/index.html`, deployed to Netlify via GitHub
Actions (same shape as the `weekly-reports`/`monthly-reports` dashboards).

## Setup

### 1. Upwork API access

1. Confirm the Email Punks Upwork client account has API access (Settings →
   API in Upwork, or check at [upwork.com/developer/keys/apply](https://www.upwork.com/developer/keys/apply)).
2. Register an app there to get a `client_id`/`client_secret`. Approval may
   take a bit — everything else in this repo works against `fixtures/` in
   the meantime (see below).
3. Once approved, run the one-time authorization script to turn your Upwork
   login into a refresh token:
   ```bash
   python3 scripts/upwork_authorize.py <client_id> <client_secret> <redirect_uri>
   ```
   Follow the prompts (see the script's docstring for what `redirect_uri`
   needs to be). It prints a refresh token at the end.
4. Find Email Punks' Upwork **organization ID** — this scopes every report
   query. (If it's not obvious from the API app's settings, the Upwork
   support team can confirm it.)

### 2. Notion

1. Create an internal integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
   — this gives you a secret token, no code required.
2. For each Notion database referenced in `pods.yaml`, open it, click
   "..." → **Connections**, and add this integration. Without this step the
   API can't see the database at all, even with a valid token.

### 3. Fill in secrets

Copy `pods.secrets.yaml.example` to `pods.secrets.yaml` (gitignored) and
fill in the five values from steps 1–2. For CI, set the same five as GitHub
Actions secrets: `UPWORK_CLIENT_ID`, `UPWORK_CLIENT_SECRET`,
`UPWORK_REFRESH_TOKEN`, `UPWORK_ORGANIZATION_ID`, `NOTION_TOKEN`.

### 4. Fill in `pods.yaml`

One example pod is filled in to show the shape — replace it with the real
roster (pods, brands, contractors, roles, task codes) whenever ready. See
the comments at the top of the file for what each field means.

### 5. Netlify

Create a Netlify site for this repo (same as Weekly/Monthly) and add
`NETLIFY_AUTH_TOKEN`/`NETLIFY_SITE_ID` as GitHub Actions secrets.

## Running

```bash
pip install -r requirements.txt
python3 main.py            # all pods, live Upwork + Notion data
python3 main.py pod-a      # just one pod, by slug
```

To check the reconciliation + rendering logic without live credentials:

```bash
python3 scripts/demo.py    # writes output/ from fixtures/
```

## How the Upwork side works

Upwork's client-facing "timesheet" report page
(`nx/reports/client/timesheet/`) is a UI over their GraphQL API
(`api.upwork.com/graphql`), not a REST/CSV endpoint. This pipeline calls the
same `timeReport` query directly — see `pod_dashboard/upwork_client.py`.

**Open question:** it's not yet confirmed whether contractors reliably put
the two-letter task code in Upwork's `task` field, the `memo` field, or
somewhere else — `pod_dashboard/reconcile.py`'s `extract_task_code()` checks
both. Once real submissions have been seen, tighten or adjust that function
to match how contractors actually log codes in practice.
