import re
from collections import defaultdict
from dataclasses import dataclass

# How close a submitted duration has to be to the task code's expected
# duration to still count as a match, rather than a duration mismatch.
# Upwork logs time in fractional hours, so a little rounding slack avoids
# flagging e.g. 59 vs 60 minutes as a mismatch.
DURATION_TOLERANCE_MINUTES = 5


@dataclass
class ReconciliationEntry:
    contractor: str
    date: str
    status: str  # match | code_mismatch | duration_mismatch | missing_in_notion | missing_in_upwork
    submitted_code: str
    submitted_minutes: float
    expected_code: str
    expected_minutes: float
    detail: str


def extract_task_code(text, valid_codes):
    """Looks for one of this role's known two-letter codes as a whole word in
    the given text (checked against both the Upwork `task` field and `memo`,
    since it's not yet confirmed which one contractors reliably use — see
    README.md). Returns None if no known code is found."""
    if not text:
        return None
    words = re.findall(r"[A-Za-z]{2,}", text.upper())
    for code in valid_codes:
        if code.upper() in words:
            return code
    return None


def _group_by_date(items, date_fn):
    grouped = defaultdict(list)
    for item in items:
        grouped[date_fn(item)].append(item)
    return grouped


def _reconcile_day(contractor_name, date, upwork_day, notion_day, valid_codes):
    unmatched_notion = list(notion_day)
    results = []

    for uw in upwork_day:
        code = extract_task_code(uw.task, valid_codes) or extract_task_code(uw.memo, valid_codes)
        submitted_minutes = uw.hours_worked * 60

        match = next((n for n in unmatched_notion if n.task_code == code), None) if code else None
        if match:
            unmatched_notion.remove(match)
            if abs(submitted_minutes - match.duration_minutes) <= DURATION_TOLERANCE_MINUTES:
                status, detail = "match", ""
            else:
                status = "duration_mismatch"
                detail = f"submitted {submitted_minutes:.0f}m, Notion expects {match.duration_minutes:.0f}m"
            results.append(
                ReconciliationEntry(
                    contractor=contractor_name,
                    date=date,
                    status=status,
                    submitted_code=code or "",
                    submitted_minutes=submitted_minutes,
                    expected_code=match.task_code,
                    expected_minutes=match.duration_minutes,
                    detail=detail,
                )
            )
        elif unmatched_notion:
            other = unmatched_notion.pop(0)
            results.append(
                ReconciliationEntry(
                    contractor=contractor_name,
                    date=date,
                    status="code_mismatch",
                    submitted_code=code or "(none found)",
                    submitted_minutes=submitted_minutes,
                    expected_code=other.task_code,
                    expected_minutes=other.duration_minutes,
                    detail=f"submitted code {code or '(none found)'!r}, Notion record is {other.task_code!r}",
                )
            )
        else:
            results.append(
                ReconciliationEntry(
                    contractor=contractor_name,
                    date=date,
                    status="missing_in_notion",
                    submitted_code=code or "(none found)",
                    submitted_minutes=submitted_minutes,
                    expected_code="",
                    expected_minutes=0,
                    detail="no matching Notion task record found for this date",
                )
            )

    for leftover in unmatched_notion:
        results.append(
            ReconciliationEntry(
                contractor=contractor_name,
                date=date,
                status="missing_in_upwork",
                submitted_code="",
                submitted_minutes=0,
                expected_code=leftover.task_code,
                expected_minutes=leftover.duration_minutes,
                detail="Notion task record has no matching Upwork submission",
            )
        )

    return results


def reconcile_pod(pod, upwork_entries, notion_records):
    """Returns a flat list of ReconciliationEntry across every contractor in
    the pod, for the date range the entries/records were fetched for."""
    all_results = []

    for contractor in pod.contractors:
        role = pod.roles[contractor.role]
        valid_codes = set(role.task_codes.keys())

        c_upwork = [e for e in upwork_entries if e.contractor_name == contractor.upwork_name]
        c_notion = [r for r in notion_records if r.contractor == contractor.name]

        upwork_by_date = _group_by_date(c_upwork, lambda e: e.date)
        notion_by_date = _group_by_date(c_notion, lambda r: r.date)

        for date in sorted(set(upwork_by_date) | set(notion_by_date)):
            all_results.extend(
                _reconcile_day(
                    contractor.name,
                    date,
                    upwork_by_date.get(date, []),
                    notion_by_date.get(date, []),
                    valid_codes,
                )
            )

    return all_results
