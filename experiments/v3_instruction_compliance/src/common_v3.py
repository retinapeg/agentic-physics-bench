"""Paths and small helpers shared by the V3 modules (standard library only).

V3 lives entirely under experiments/v3_instruction_compliance/. It imports the frozen V1/V2 modules from
the repository's src/ directory unchanged (ls_slope, the fit_line tool and its validator, the parser and
grader, echo_safe); it never writes there.
"""
import hashlib
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent          # experiments/v3_instruction_compliance/src
EXP = SRC.parent                               # experiments/v3_instruction_compliance
ROOT = EXP.parents[1]                          # repository root
for _p in (str(ROOT / "src"), str(SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PROMPTS = EXP / "prompts"
DATA = EXP / "data"
RESULTS = EXP / "results"
RAW = RESULTS / "raw"                          # gitignored: full CLI output carries session metadata
V2_PROMPTS = ROOT / "prompts" / "v2"
EXPERIMENT_VERSION = "v3.0.1"


def sha256_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    path = Path(path)
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def to_jsonl(rows):
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)


def append_jsonl(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")
