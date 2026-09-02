#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from pod_dashboard.config import PodConfigError, load_pods, load_roles, load_secrets
from pod_dashboard.ledger import load_used_codes, save_used_codes
from pod_dashboard.notion_client import NotionClient
from pod_dashboard.page import render_index_page, render_pod_page
from pod_dashboard.reconcile import reconcile_pod, unknown_handles as find_unknown_handles
from pod_dashboard.upwork_csv import parse_timesheet_csv

OUTPUT_DIR = Path(__file__).parent / "output"


def run_for_pod(pod, submissions, notion_client):
    notion_records = []
    for brand in pod.brands:
        for database_id in brand.notion_database_ids:
            records = notion_client.query_task_records(database_id, brand.notion_property_map)
            print(f"[{pod.name}] {brand.name} / {database_id}: pulled {len(records)} Task Code(s) from Notion")
            notion_records.extend(records)
    print(f"[{pod.name}] {len(notion_records)} Notion task code(s) total across {len(pod.brands)} brand(s)")

    used_codes = load_used_codes(pod.slug)
    reconciliation = reconcile_pod(pod, submissions, notion_records, used_codes)
    save_used_codes(pod.slug, used_codes)  # reconcile_pod mutates used_codes with any newly verified code
    return reconciliation


def main():
    parser = argparse.ArgumentParser(description="Reconcile Upwork time submissions against Notion task records.")
    parser.add_argument("csv_path", help="Path to an exported Upwork timesheet CSV (nx/reports/client/timesheet/)")
    parser.add_argument("pods", nargs="*", help="Only run these pod slugs (default: all pods in pods.yaml)")
    args = parser.parse_args()

    try:
        all_pods = load_pods()
        roles = load_roles()
        secrets = load_secrets()
    except PodConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    pods = [p for p in all_pods if p.slug in args.pods] if args.pods else all_pods
    if not pods:
        print("No matching pods found in pods.yaml.", file=sys.stderr)
        sys.exit(1)

    submissions = parse_timesheet_csv(args.csv_path)
    notion_client = NotionClient(secrets.notion_token)

    unknown = find_unknown_handles(all_pods, submissions)
    if unknown:
        print(f"Warning: unrecognized Upwork handle(s) in CSV: {', '.join(unknown)}", file=sys.stderr)

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    (OUTPUT_DIR / "index.html").write_text(render_index_page(all_pods))

    succeeded, failed = [], []
    for pod in pods:
        print(f"[{pod.name}] Fetching Notion data and reconciling...")
        try:
            reconciliation = run_for_pod(pod, submissions, notion_client)
            pod_dir = OUTPUT_DIR / pod.slug
            pod_dir.mkdir(parents=True, exist_ok=True)
            (pod_dir / "index.html").write_text(render_pod_page(pod, reconciliation, all_pods, roles, unknown))
            hours_mismatches = sum(1 for c in reconciliation.hours_checks if c.status == "mismatch")
            code_mismatches = sum(1 for c in reconciliation.code_checks if c.status == "mismatch")
            print(f"[{pod.name}] {hours_mismatches} hours mismatches, {code_mismatches} code mismatches")
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
