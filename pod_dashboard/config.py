import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
PODS_YAML = ROOT / "pods.yaml"
SECRETS_YAML = ROOT / "pods.secrets.yaml"
POD_DATA_DIR = ROOT / "pod_data"

SECRET_ENV_VARS = {
    "notion_token": "NOTION_TOKEN",
}


class PodConfigError(RuntimeError):
    pass


@dataclass
class TaskCode:
    code: str
    label: str
    minutes: int


@dataclass
class Role:
    name: str
    task_codes: dict  # code -> TaskCode


@dataclass(frozen=True)
class Contractor:
    name: str
    upwork_handle: str
    role: str


@dataclass
class Brand:
    name: str
    notion_database_id: str
    notion_property_map: dict


@dataclass
class Pod:
    slug: str
    name: str
    brands: list  # Brand
    contractors: list  # Contractor
    roles: dict  # role name -> Role


@dataclass
class Secrets:
    notion_token: str


def load_secrets():
    """Secrets come from individual env vars (CI) if set, otherwise a local
    pods.secrets.yaml file (gitignored, never committed)."""
    env_values = {key: os.environ.get(var) for key, var in SECRET_ENV_VARS.items()}
    if all(env_values.values()):
        return Secrets(**env_values)

    if SECRETS_YAML.exists():
        with open(SECRETS_YAML) as f:
            raw = yaml.safe_load(f) or {}
        try:
            return Secrets(**{key: raw.get(key) for key in SECRET_ENV_VARS})
        except TypeError as e:
            raise PodConfigError(f"pods.secrets.yaml is missing a required field: {e}")

    raise PodConfigError(
        "No secrets found — set the NOTION_TOKEN env var, or copy "
        "pods.secrets.yaml.example to pods.secrets.yaml and fill it in."
    )


def _build_role(name, entry):
    task_codes = {
        code: TaskCode(code=code, label=data["label"], minutes=data["minutes"])
        for code, data in (entry.get("task_codes") or {}).items()
    }
    return Role(name=name, task_codes=task_codes)


def _build_brand(entry):
    try:
        return Brand(
            name=entry["name"],
            notion_database_id=entry["notion_database_id"],
            notion_property_map=entry["notion_property_map"],
        )
    except KeyError as e:
        raise PodConfigError(f"brand entry {entry!r} is missing required field {e}")


def _load_pod_overlay(slug, pod_data_dir):
    """Admin-page-managed contractor additions for one pod — written
    straight to pod_data/{slug}.json by the Admin page via the GitHub
    Contents API (see admin_page.py). Absent for any pod the Admin page
    hasn't touched. A slug with no pods.yaml entry at all becomes a
    brand-new pod defined entirely by its overlay file."""
    path = pod_data_dir / f"{slug}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _build_contractors(entries, roles, slug):
    contractors = []
    for c in entries:
        contractor = Contractor(name=c["name"], upwork_handle=c["upwork_handle"], role=c["role"])
        if contractor.role not in roles:
            raise PodConfigError(
                f"pod {slug!r}: contractor {contractor.name!r} has role {contractor.role!r}, "
                f"which isn't defined in the top-level roles"
            )
        contractors.append(contractor)
    return contractors


def load_roles(path=PODS_YAML):
    """Roles (and their task codes) are shared across every pod, defined once
    at the top level rather than duplicated per pod. Exposed standalone
    (not just via load_pods) so callers like the Admin page can get the role
    list without needing any pod to exist."""
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return {name: _build_role(name, data) for name, data in (raw.get("roles") or {}).items()}


def load_pods(path=PODS_YAML, pod_data_dir=POD_DATA_DIR):
    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    roles = load_roles(path)

    pods = []
    seen_slugs = set()
    for entry in raw.get("pods", []):
        try:
            slug = entry["slug"]
        except KeyError as e:
            raise PodConfigError(f"pods.yaml entry {entry!r} is missing required field {e}")

        seen_slugs.add(slug)
        overlay = _load_pod_overlay(slug, pod_data_dir)
        existing_handles = {c["upwork_handle"] for c in entry.get("contractors", [])}
        overlay_contractors = [
            c for c in overlay.get("contractors", []) if c.get("upwork_handle") not in existing_handles
        ]

        contractors = _build_contractors(entry.get("contractors", []) + overlay_contractors, roles, slug)
        brands = [_build_brand(b) for b in entry.get("brands", [])]

        pods.append(Pod(slug=slug, name=entry.get("name", slug), brands=brands, contractors=contractors, roles=roles))

    # Pods created entirely through the Admin page (assigning someone to a
    # pod slug that doesn't exist in pods.yaml yet) live only in
    # pod_data/{slug}.json — no brands until those are configured by hand.
    if pod_data_dir.exists():
        for data_path in sorted(pod_data_dir.glob("*.json")):
            slug = data_path.stem
            if slug in seen_slugs:
                continue
            overlay = _load_pod_overlay(slug, pod_data_dir)
            if not overlay.get("contractors"):
                continue
            contractors = _build_contractors(overlay["contractors"], roles, slug)
            pods.append(Pod(slug=slug, name=overlay.get("name", slug), brands=[], contractors=contractors, roles=roles))

    return pods
