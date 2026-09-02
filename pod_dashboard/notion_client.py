from dataclasses import dataclass

import requests

API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


@dataclass
class NotionTaskRecord:
    contractor: str
    task_code: str
    date: str


class NotionError(RuntimeError):
    pass


class NotionClient:
    def __init__(self, token):
        self.token = token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _query_database_pages(self, database_id):
        pages = []
        cursor = None
        while True:
            body = {"start_cursor": cursor} if cursor else {}
            resp = requests.post(f"{API_BASE}/databases/{database_id}/query", headers=self._headers(), json=body)
            if not resp.ok:
                raise NotionError(f"Notion query failed for database {database_id} ({resp.status_code}): {resp.text}")

            data = resp.json()
            pages.extend(data["results"])
            if not data.get("has_more"):
                break
            cursor = data["next_cursor"]
        return pages

    def query_task_records(self, database_id, property_map):
        """property_map maps our field names (contractor, task_code, date) to
        this database's actual Notion property names, since schemas vary per
        brand — see pods.yaml. task_code is the full code Notion generated
        for that task (e.g. "TB11426081516482608251636"), pulled verbatim —
        this is the master list a contractor's Upwork submission gets
        checked against for an exact match. Expected duration for a task
        code's two-letter prefix still comes from pods.yaml's task_codes,
        not from Notion."""
        records = []
        for page in self._query_database_pages(database_id):
            props = page["properties"]
            records.append(
                NotionTaskRecord(
                    contractor=_extract_text(props.get(property_map["contractor"])),
                    task_code=_extract_text(props.get(property_map["task_code"])).strip(),
                    date=_extract_date(props.get(property_map["date"])),
                )
            )
        return records


def _extract_text(prop):
    if not prop:
        return ""
    prop_type = prop.get("type")
    if prop_type == "title":
        return "".join(t["plain_text"] for t in prop["title"])
    if prop_type == "rich_text":
        return "".join(t["plain_text"] for t in prop["rich_text"])
    if prop_type == "select":
        return (prop.get("select") or {}).get("name", "")
    if prop_type == "people":
        people = prop.get("people") or []
        return people[0]["name"] if people else ""
    return ""


def _extract_date(prop):
    if not prop or prop.get("type") != "date":
        return ""
    date = prop.get("date")
    return date["start"] if date else ""
