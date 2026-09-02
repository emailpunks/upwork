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
class CodeCheck:
    """One code stamp the contractor submitted on Upwork: does it exactly
    match a code Notion generated for them, and hasn't already been
    claimed in a previous (or this) run?"""

    contractor: str
    date_from: str
    date_to: str
    code: str  # full code as submitted, e.g. "TB11426081516482608251636"
    label: str  # task_codes' label for its two-letter prefix; "" if unrecognized
    status: str  # match | mismatch
    detail: str


@dataclass
class PodReconciliation:
    hours_checks: list = field(default_factory=list)
    code_checks: list = field(default_factory=list)


def _check_hours(contractor, role, submission):
    prefixes = Counter(code[:2].upper() for code in submission.codes)
    unrecognized_codes = sorted(p for p in prefixes if p not in role.task_codes)
    expected_minutes = sum(n * role.task_codes[p].minutes for p, n in prefixes.items() if p in role.task_codes)
    submitted_minutes = submission.hours * 60

    problems = []
    if unrecognized_codes:
        problems.append(f"unrecognized code(s) {', '.join(unrecognized_codes)}")
    if submission.unrecognized_text:
        problems.append(f"non-code text in memo: {'; '.join(submission.unrecognized_text)}")
    if abs(expected_minutes - submitted_minutes) > HOURS_TOLERANCE_MINUTES:
        problems.append(f"submitted {submitted_minutes:.0f}m, codes add up to {expected_minutes:.0f}m")

    code_summary = ", ".join(f"{prefix}x{n}" for prefix, n in sorted(prefixes.items()))
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


def _check_codes(contractor, role, date_from, date_to, upwork_codes, notion_codes, used_codes):
    """notion_codes: the full set of codes Notion has for this pod (the
    "master list") — there's no per-contractor assignment in Notion, so any
    pod member can legitimately submit any of these codes, just not the
    same one twice. used_codes: this pod's whole ledger, keyed by code then
    by contractor name (see ledger.py) — mutated in place with any newly
    verified code, so the caller can save it back out."""
    checks = []
    seen_this_batch = set()

    for code in upwork_codes:
        prefix = code[:2].upper()
        task_code = role.task_codes.get(prefix)
        label = task_code.label if task_code else ""
        claimed_by = used_codes.get(code, {})

        if code in seen_this_batch:
            status, detail = "mismatch", "submitted more than once in this batch"
        elif contractor.name in claimed_by:
            status = "mismatch"
            detail = f"you already claimed this code ({claimed_by[contractor.name]})"
        elif code not in notion_codes:
            status, detail = "mismatch", "no exact match in the Notion master list"
        else:
            status, detail = "match", "verified against Notion"
            used_codes.setdefault(code, {})[contractor.name] = f"{date_from} to {date_to}"

        seen_this_batch.add(code)
        checks.append(
            CodeCheck(
                contractor=contractor.name,
                date_from=date_from,
                date_to=date_to,
                code=code,
                label=label,
                status=status,
                detail=detail,
            )
        )
    return checks


def reconcile_pod(pod, submissions, notion_records, used_codes):
    """submissions may include rows for contractors outside this pod (the
    same CSV covers everyone) — those are silently skipped here, not
    reported as unknown. Call unknown_handles() separately across all pods
    to catch handles that aren't anyone's.

    used_codes: this pod's ledger (see ledger.py), mutated in place with
    any newly verified code — the caller is responsible for persisting it
    after this returns."""
    by_handle = {c.upwork_handle: c for c in pod.contractors}
    notion_codes = {r.task_code for r in notion_records}

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
        role = pod.roles[contractor.role]
        codes = [code for s in period_submissions for code in s.codes]
        result.code_checks.extend(_check_codes(contractor, role, date_from, date_to, codes, notion_codes, used_codes))

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
