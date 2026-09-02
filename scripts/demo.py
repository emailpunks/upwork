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
from pod_dashboard.ledger import load_used_codes
from pod_dashboard.notion_client import NotionTaskRecord, drop_codes_before
from pod_dashboard.page import render_index_page, render_pod_page
from pod_dashboard.reconcile import reconcile_pod, unknown_handles
from pod_dashboard.upwork_csv import parse_timesheet_csv

FIXTURES = ROOT / "fixtures"
OUTPUT_DIR = ROOT / "output"


def main():
    pods = load_pods(pod_data_dir=FIXTURES / "pod_data")
    roles = load_roles()

    submissions = parse_timesheet_csv(FIXTURES / "sample_timesheet.csv")
    all_notion_records = [
        NotionTaskRecord(**row) for row in json.loads((FIXTURES / "notion_task_records.json").read_text())
    ]

    unknown = unknown_handles(pods, submissions)
    if unknown:
        print(f"Unrecognized handle(s): {', '.join(unknown)}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "index.html").write_text(render_index_page(pods))

    for pod in pods:
        # Loaded from fixtures/used_codes/ but never written back, so re-running
        # this script doesn't mutate the fixture — the ledger's persistence is
        # exercised by main.py's real runs, not this visual-check script.
        used_codes = load_used_codes(pod.slug, used_codes_dir=FIXTURES / "used_codes")
        notion_records, _ = drop_codes_before(all_notion_records, pod.ignore_codes_before)
        reconciliation = reconcile_pod(pod, submissions, notion_records, used_codes)
        notion_codes = {r.task_code for r in notion_records}
        pod_dir = OUTPUT_DIR / pod.slug
        pod_dir.mkdir(parents=True, exist_ok=True)
        page_html = render_pod_page(pod, reconciliation, pods, roles, unknown, notion_codes, used_codes)
        (pod_dir / "index.html").write_text(page_html)
        hours_mismatches = sum(1 for c in reconciliation.hours_checks if c.status == "mismatch")
        code_mismatches = sum(1 for c in reconciliation.code_checks if c.status == "mismatch")
        print(f"[{pod.name}] {hours_mismatches} hours mismatches, {code_mismatches} code mismatches -> {pod_dir / 'index.html'}")


if __name__ == "__main__":
    main()
