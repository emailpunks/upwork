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
from pod_dashboard.page import render_index_page, render_pod_page
from pod_dashboard.reconcile import reconcile_pod, unknown_handles
from pod_dashboard.upwork_csv import parse_timesheet_csv

FIXTURES = ROOT / "fixtures"
OUTPUT_DIR = ROOT / "output"


def main():
    pods = load_pods(pod_data_dir=FIXTURES / "pod_data")
    roles = load_roles()

    submissions = parse_timesheet_csv(FIXTURES / "sample_timesheet.csv")
    notion_records = [
        NotionTaskRecord(**row) for row in json.loads((FIXTURES / "notion_task_records.json").read_text())
    ]

    unknown = unknown_handles(pods, submissions)
    if unknown:
        print(f"Unrecognized handle(s): {', '.join(unknown)}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "index.html").write_text(render_index_page(pods))

    for pod in pods:
        reconciliation = reconcile_pod(pod, submissions, notion_records)
        pod_dir = OUTPUT_DIR / pod.slug
        pod_dir.mkdir(parents=True, exist_ok=True)
        (pod_dir / "index.html").write_text(render_pod_page(pod, reconciliation, pods, roles, unknown))
        hours_mismatches = sum(1 for c in reconciliation.hours_checks if c.status == "mismatch")
        code_mismatches = sum(1 for c in reconciliation.code_checks if c.status == "mismatch")
        print(f"[{pod.name}] {hours_mismatches} hours mismatches, {code_mismatches} code-count mismatches -> {pod_dir / 'index.html'}")


if __name__ == "__main__":
    main()
