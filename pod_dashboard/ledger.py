import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
USED_CODES_DIR = ROOT / "used_codes"

# Once a code is confirmed as a legitimate, exact match against Notion's
# master list, it's recorded here so it can never be matched again in a
# future run — prevents a contractor re-submitting the same code (copied
# from a prior week, or pasted twice) to double-claim it. This is a
# read-only relationship with Notion: nothing is ever written back there,
# so this file is the only record of what's already been claimed.


def load_used_codes(slug, used_codes_dir=USED_CODES_DIR):
    path = used_codes_dir / f"{slug}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_used_codes(slug, used_codes, used_codes_dir=USED_CODES_DIR):
    used_codes_dir.mkdir(parents=True, exist_ok=True)
    path = used_codes_dir / f"{slug}.json"
    path.write_text(json.dumps(used_codes, indent=2, sort_keys=True) + "\n")
