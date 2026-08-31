from dataclasses import dataclass

import requests

TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"
GRAPHQL_URL = "https://api.upwork.com/graphql"

# Selects exactly the fields reconcile.py needs: who worked, what they logged
# it as, their notes, and how long they say it took. See README.md for how
# this query was found — Upwork's client-facing "timesheet" report page
# (nx/reports/client/timesheet/) is a UI over this same query.
TIME_REPORT_QUERY = """
query TimeReport($filter: TimeReportFilter) {
  timeReport(filter: $filter) {
    dateWorkedOn
    freelancer {
      name
    }
    task
    taskDescription
    memo
    totalHoursWorked
  }
}
"""


@dataclass
class TimeReportEntry:
    contractor_name: str
    date: str
    task: str
    task_description: str
    memo: str
    hours_worked: float


class UpworkError(RuntimeError):
    pass


class UpworkClient:
    def __init__(self, client_id, client_secret, refresh_token, organization_id):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.organization_id = organization_id
        self._access_token = None

    def _get_access_token(self):
        if self._access_token:
            return self._access_token

        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        if not resp.ok:
            raise UpworkError(f"Token refresh failed ({resp.status_code}): {resp.text}")

        self._access_token = resp.json()["access_token"]
        return self._access_token

    def _graphql(self, query, variables):
        resp = requests.post(
            GRAPHQL_URL,
            headers={"Authorization": f"Bearer {self._get_access_token()}"},
            json={"query": query, "variables": variables},
        )
        if not resp.ok:
            raise UpworkError(f"GraphQL request failed ({resp.status_code}): {resp.text}")

        body = resp.json()
        if body.get("errors"):
            raise UpworkError(f"GraphQL errors: {body['errors']}")
        return body["data"]

    def fetch_time_report(self, date_from, date_to, contract_ids=None):
        """date_from/date_to: 'YYYY-MM-DD'. contract_ids, if given, restricts
        the report to those Upwork contracts; otherwise every contract under
        the organization is included."""
        filter_ = {
            "organizationId_eq": self.organization_id,
            "timeReportDate_bt": {"rangeStart": date_from, "rangeEnd": date_to},
        }
        if contract_ids:
            filter_["contractIds"] = contract_ids

        data = self._graphql(TIME_REPORT_QUERY, {"filter": filter_})

        entries = []
        for row in data["timeReport"]:
            entries.append(
                TimeReportEntry(
                    contractor_name=(row.get("freelancer") or {}).get("name", ""),
                    date=row["dateWorkedOn"],
                    task=row.get("task") or "",
                    task_description=row.get("taskDescription") or "",
                    memo=row.get("memo") or "",
                    hours_worked=row.get("totalHoursWorked") or 0.0,
                )
            )
        return entries
