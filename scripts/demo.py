#!/usr/bin/env python3
"""Runs the reconcile + render pipeline against fixtures/ instead of a real
CSV export and live Notion calls, so the logic can be checked visually
without either. See README.md."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from pod_dashboard.config import load_pods, load_roles
from pod_dashboard.notion_client import NotionTaskRecord
from pod_dashboard.page import render_page
from pod_dashboard.reconcile import reconcile_pod, unknown_handles
from pod_dashboard.upwork_csv import parse_timesheet_csv

FIXTURES = ROOT / "fixtures"
OUTPUT_DIR = ROOT / "output"


def main():
    pods = load_pods(pod_data_dir=FIXTURES / "pod_data")

    submissions = parse_timesheet_csv(FIXTURES / "sample_timesheet.csv")
    notion_records = [
        NotionTaskRecord(**row) for row in json.loads((FIXTURES / "notion_task_records.json").read_text())
    ]

    unknown = unknown_handles(pods, submissions)
    if unknown:
        print(f"Unrecognized handle(s): {', '.join(unknown)}")

    pods_with_reconciliation = []
    for pod in pods:
        reconciliation = reconcile_pod(pod, submissions, notion_records)
        pods_with_reconciliation.append((pod, reconciliation))
        hours_mismatches = sum(1 for c in reconciliation.hours_checks if c.status == "mismatch")
        code_mismatches = sum(1 for c in reconciliation.code_checks if c.status == "mismatch")
        print(f"[{pod.name}] {hours_mismatches} hours mismatches, {code_mismatches} code-count mismatches")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / "index.html"
    out_path.write_text(render_page(pods_with_reconciliation, unknown, pods, load_roles()))
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
