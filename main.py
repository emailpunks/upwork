#!/usr/bin/env python3
import sys
from datetime import date, timedelta
from pathlib import Path

from pod_dashboard.config import PodConfigError, load_pods, load_secrets
from pod_dashboard.notion_client import NotionClient
from pod_dashboard.reconcile import reconcile_pod
from pod_dashboard.render import render_index, render_pod_page
from pod_dashboard.upwork_client import UpworkClient

OUTPUT_DIR = Path(__file__).parent / "output"

# How far back each run looks. A contractor's Upwork submission and their
# Notion task record won't always land in the same run, so this window is
# wider than the daily/weekly cadence the pipeline is expected to run at.
LOOKBACK_DAYS = 14


def run_for_pod(pod, upwork_client, notion_client, date_from, date_to):
    contract_ids = [cid for brand in pod.brands for cid in brand.upwork_contract_ids] or None
    upwork_entries = upwork_client.fetch_time_report(date_from, date_to, contract_ids=contract_ids)

    notion_records = []
    for brand in pod.brands:
        notion_records.extend(notion_client.query_task_records(brand.notion_database_id, brand.notion_property_map))

    entries = reconcile_pod(pod, upwork_entries, notion_records)

    pod_dir = OUTPUT_DIR / pod.slug
    pod_dir.mkdir(parents=True, exist_ok=True)
    (pod_dir / "index.html").write_text(render_pod_page(pod, entries))
    return entries


def main():
    try:
        pods = load_pods()
        secrets = load_secrets()
    except PodConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    only = set(sys.argv[1:])
    if only:
        pods = [p for p in pods if p.slug in only]
    if not pods:
        print("No matching pods found in pods.yaml.", file=sys.stderr)
        sys.exit(1)

    upwork_client = UpworkClient(
        client_id=secrets.upwork_client_id,
        client_secret=secrets.upwork_client_secret,
        refresh_token=secrets.upwork_refresh_token,
        organization_id=secrets.upwork_organization_id,
    )
    notion_client = NotionClient(secrets.notion_token)

    date_to = date.today()
    date_from = date_to - timedelta(days=LOOKBACK_DAYS)

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    (OUTPUT_DIR / "index.html").write_text(render_index(pods))

    succeeded, failed = [], []
    for pod in pods:
        print(f"[{pod.name}] Fetching Upwork + Notion data...")
        try:
            entries = run_for_pod(pod, upwork_client, notion_client, str(date_from), str(date_to))
            mismatches = sum(1 for e in entries if e.status != "match")
            print(f"[{pod.name}] {len(entries)} entries, {mismatches} mismatches")
            succeeded.append(pod.name)
        except Exception as e:
            print(f"[{pod.name}] FAILED: {e}", file=sys.stderr)
            failed.append(pod.name)

    print(f"\n{len(succeeded)} succeeded, {len(failed)} failed.")
    if failed:
        print(f"Failed pods: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
