"""V4 paths, canonical evidence, and read-only access to frozen infrastructure."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
RESULTS = ROOT / "results"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments/v3_instruction_compliance/src"))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def write_new(path, value, private=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if private else 0o644)
    with os.fdopen(fd, "w") as out:
        out.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def frozen_code():
    paths = list((ROOT / "src").glob("*.py")) + [ROOT / "PROTOCOL.md"]
    paths += [REPO / p for p in ("src/models.py", "src/evaluate.py", "src/tasks.py", "src/tools.py",
              "experiments/v3_instruction_compliance/src/controls_v3.py",
              "experiments/v3_instruction_compliance/src/models_v3.py",
              "experiments/v3_instruction_compliance/src/common_v3.py")]
    return {str(p.relative_to(REPO)): file_hash(p) for p in sorted(paths) if p.exists()}
