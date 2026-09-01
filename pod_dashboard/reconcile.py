from collections import Counter, defaultdict
from dataclasses import dataclass, field

# How close a submission's total minutes has to be to what its code stamps
# add up to, to still count as a match rather than an hours mismatch. Upwork
# logs time in fractional hours, so a little rounding slack avoids flagging
# e.g. 59 vs 60 minutes.
HOURS_TOLERANCE_MINUTES = 1


@dataclass
class HoursCheck:
    """One Upwork CSV row (a contractor's submission for a period): does the
    total time they submitted match what their logged code stamps add up
    to, using each code's fixed expected duration from pods.yaml?"""

    contractor: str
    date_from: str
    date_to: str
    submitted_minutes: float
    expected_minutes: float
    status: str  # match | mismatch
    detail: str


@dataclass
class CodeCountCheck:
    """One (contractor, period, code) combination: did they log this code on
    Upwork the same number of times Notion shows it was actually completed?"""

    contractor: str
    date_from: str
    date_to: str
    code: str
    upwork_count: int
    notion_count: int
    status: str  # match | mismatch
    detail: str


@dataclass
class PodReconciliation:
    hours_checks: list = field(default_factory=list)
    code_checks: list = field(default_factory=list)


def _date_in_range(date, date_from, date_to):
    return date_from <= date <= date_to


def _check_hours(contractor, role, submission):
    counts = Counter(submission.codes)
    unrecognized_codes = sorted(c for c in counts if c not in role.task_codes)
    expected_minutes = sum(counts[c] * role.task_codes[c].minutes for c in counts if c in role.task_codes)
    submitted_minutes = submission.hours * 60

    problems = []
    if unrecognized_codes:
        problems.append(f"unrecognized code(s) {', '.join(unrecognized_codes)}")
    if submission.unrecognized_text:
        problems.append(f"non-code text in memo: {'; '.join(submission.unrecognized_text)}")
    if abs(expected_minutes - submitted_minutes) > HOURS_TOLERANCE_MINUTES:
        problems.append(f"submitted {submitted_minutes:.0f}m, codes add up to {expected_minutes:.0f}m")

    code_summary = ", ".join(f"{code}x{n}" for code, n in sorted(counts.items()))
    status = "mismatch" if problems else "match"
    detail = "; ".join(problems) if problems else code_summary

    return HoursCheck(
        contractor=contractor.name,
        date_from=submission.date_from,
        date_to=submission.date_to,
        submitted_minutes=submitted_minutes,
        expected_minutes=expected_minutes,
        status=status,
        detail=detail,
    )


def _check_code_counts(contractor, date_from, date_to, upwork_codes, notion_records):
    upwork_counts = Counter(upwork_codes)
    notion_counts = Counter(
        r.task_code
        for r in notion_records
        if r.contractor == contractor.name and _date_in_range(r.date, date_from, date_to)
    )

    checks = []
    for code in sorted(set(upwork_counts) | set(notion_counts)):
        uw, no = upwork_counts.get(code, 0), notion_counts.get(code, 0)
        if uw == no:
            status, detail = "match", f"{uw}x on both sides"
        elif uw > no:
            status, detail = "mismatch", f"{uw}x submitted on Upwork, only {no}x in Notion"
        else:
            status, detail = "mismatch", f"{no}x completed in Notion, only {uw}x submitted on Upwork"
        checks.append(
            CodeCountCheck(
                contractor=contractor.name,
                date_from=date_from,
                date_to=date_to,
                code=code,
                upwork_count=uw,
                notion_count=no,
                status=status,
                detail=detail,
            )
        )
    return checks


def reconcile_pod(pod, submissions, notion_records):
    """submissions may include rows for contractors outside this pod (the
    same CSV covers everyone) — those are silently skipped here, not
    reported as unknown. Call unknown_handles() separately across all pods
    to catch handles that aren't anyone's."""
    by_handle = {c.upwork_handle: c for c in pod.contractors}

    result = PodReconciliation()
    by_contractor_period = defaultdict(list)  # (contractor, date_from, date_to) -> [submission, ...]

    for submission in submissions:
        contractor = by_handle.get(submission.contractor_handle)
        if not contractor:
            continue

        role = pod.roles[contractor.role]
        result.hours_checks.append(_check_hours(contractor, role, submission))
        by_contractor_period[(contractor, submission.date_from, submission.date_to)].append(submission)

    for (contractor, date_from, date_to), period_submissions in by_contractor_period.items():
        codes = [code for s in period_submissions for code in s.codes]
        result.code_checks.extend(_check_code_counts(contractor, date_from, date_to, codes, notion_records))

    return result


def unknown_handles(all_pods, submissions):
    """Upwork handles present in the CSV that don't belong to any contractor
    in any pod — likely a typo in pods.yaml or someone new who hasn't been
    added yet."""
    known = {c.upwork_handle for pod in all_pods for c in pod.contractors}
    seen = []
    for submission in submissions:
        if submission.contractor_handle not in known and submission.contractor_handle not in seen:
            seen.append(submission.contractor_handle)
    return seen
