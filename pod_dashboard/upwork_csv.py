import csv
import re
from dataclasses import dataclass, field

# Matches how the contractor's Upwork handle appears in the CSV's "Talent"
# column: "Jane Doe (abc12de)".
HANDLE_RE = re.compile(r"\(([^)]+)\)\s*$")

# Each stamp in the Memo field looks like "CT11626081516482608231519" — a
# two-letter task code followed by digits. The full stamp (not just the
# prefix) is kept, since it's checked for an exact match against the full
# code Notion generated for that task — see reconcile.py. Stamps can be
# separated by newlines OR spaces within the same memo, so this searches
# the whole memo text rather than splitting into lines first.
STAMP_RE = re.compile(r"[A-Za-z]{2}\d+")


@dataclass
class UpworkSubmission:
    contractor_handle: str
    date_from: str
    date_to: str
    hours: float
    codes: list = field(default_factory=list)  # one entry per stamp, full string, e.g. ["ES12326081517442608251636"]
    unrecognized_text: list = field(default_factory=list)  # memo content that wasn't a code stamp


def _extract_handle(talent):
    m = HANDLE_RE.search(talent)
    return m.group(1) if m else talent


def _parse_memo(memo):
    codes = [m.group(0) for m in STAMP_RE.finditer(memo)]
    # Whatever's left after removing every matched stamp is free text the
    # contractor typed instead of (or alongside) a code stamp — worth
    # surfacing, since it's real logged time with no code to check it against.
    leftover = STAMP_RE.sub("", memo)
    unrecognized = [line.strip() for line in leftover.splitlines() if line.strip()]
    return codes, unrecognized


def parse_timesheet_csv(path):
    """Parses an export from Upwork's client timesheet report
    (nx/reports/client/timesheet/): one row per contractor per week, with a
    Memo field listing every task code stamp logged that week."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        submissions = []
        for row in reader:
            codes, unrecognized = _parse_memo(row["Memo"])
            submissions.append(
                UpworkSubmission(
                    contractor_handle=_extract_handle(row["Talent"]),
                    date_from=row["Date from"],
                    date_to=row["Date to"],
                    hours=float(row["Hours"]),
                    codes=codes,
                    unrecognized_text=unrecognized,
                )
            )
    return submissions
