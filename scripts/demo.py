#!/usr/bin/env python3
"""Runs the reconcile + render pipeline against fixtures/ instead of live
Upwork/Notion calls, so the dashboard can be checked visually before Upwork
API credentials exist. See README.md."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from pod_dashboard.config import load_pods
from pod_dashboard.notion_client import NotionTaskRecord
from pod_dashboard.reconcile import reconcile_pod
from pod_dashboard.render import render_index, render_pod_page
from pod_dashboard.upwork_client import TimeReportEntry

FIXTURES = ROOT / "fixtures"
OUTPUT_DIR = ROOT / "output"


def main():
    pods = load_pods()

    upwork_entries = [TimeReportEntry(**row) for row in json.loads((FIXTURES / "upwork_time_report.json").read_text())]
    notion_records = [
        NotionTaskRecord(**row) for row in json.loads((FIXTURES / "notion_task_records.json").read_text())
    ]

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "index.html").write_text(render_index(pods))

    for pod in pods:
        entries = reconcile_pod(pod, upwork_entries, notion_records)
        pod_dir = OUTPUT_DIR / pod.slug
        pod_dir.mkdir(parents=True, exist_ok=True)
        (pod_dir / "index.html").write_text(render_pod_page(pod, entries))
        mismatches = sum(1 for e in entries if e.status != "match")
        print(f"[{pod.name}] {len(entries)} entries, {mismatches} mismatches -> {pod_dir / 'index.html'}")


if __name__ == "__main__":
    main()
