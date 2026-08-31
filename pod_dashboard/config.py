import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
PODS_YAML = ROOT / "pods.yaml"
SECRETS_YAML = ROOT / "pods.secrets.yaml"

SECRET_ENV_VARS = {
    "upwork_client_id": "UPWORK_CLIENT_ID",
    "upwork_client_secret": "UPWORK_CLIENT_SECRET",
    "upwork_refresh_token": "UPWORK_REFRESH_TOKEN",
    "upwork_organization_id": "UPWORK_ORGANIZATION_ID",
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


@dataclass
class Contractor:
    name: str
    upwork_name: str
    role: str


@dataclass
class Brand:
    name: str
    notion_database_id: str
    notion_property_map: dict
    upwork_contract_ids: list = field(default_factory=list)


@dataclass
class Pod:
    slug: str
    name: str
    brands: list  # Brand
    contractors: list  # Contractor
    roles: dict  # role name -> Role


@dataclass
class Secrets:
    upwork_client_id: str
    upwork_client_secret: str
    upwork_refresh_token: str
    upwork_organization_id: str
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
        "No secrets found — set the UPWORK_*/NOTION_TOKEN env vars, or copy "
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
            upwork_contract_ids=entry.get("upwork_contract_ids", []),
        )
    except KeyError as e:
        raise PodConfigError(f"brand entry {entry!r} is missing required field {e}")


def load_pods(path=PODS_YAML):
    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    pods = []
    for entry in raw.get("pods", []):
        try:
            slug = entry["slug"]
        except KeyError as e:
            raise PodConfigError(f"pods.yaml entry {entry!r} is missing required field {e}")

        roles = {name: _build_role(name, data) for name, data in (entry.get("roles") or {}).items()}
        contractors = [
            Contractor(name=c["name"], upwork_name=c["upwork_name"], role=c["role"])
            for c in entry.get("contractors", [])
        ]
        brands = [_build_brand(b) for b in entry.get("brands", [])]

        for c in contractors:
            if c.role not in roles:
                raise PodConfigError(
                    f"pod {slug!r}: contractor {c.name!r} has role {c.role!r}, "
                    f"which isn't defined in this pod's roles"
                )

        pods.append(Pod(slug=slug, name=entry.get("name", slug), brands=brands, contractors=contractors, roles=roles))

    return pods
