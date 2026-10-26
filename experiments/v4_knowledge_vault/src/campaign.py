"""Prospective V4 held-out freezes. No campaign is created or run automatically."""
import json
from pathlib import Path
import re
import secrets
import uuid

import common
from adapter import preflight
from engine import Run, validate_config


def freeze(config, cases=10, identity=None, directory=None):
    if type(cases) is not int or not 1 <= cases <= 100:
        raise ValueError("Choose 1–100 independent cases; each is paired across both defences")
    config = validate_config({**config,"split":"heldout"})
    identity = identity or preflight()
    if not identity.get("ready"):
        raise ValueError("CLI preflight must pass before freezing a campaign")
    cid = "campaign-"+uuid.uuid4().hex[:16]
    folder = (directory or common.ROOT/"data/campaigns")/cid
    seeds = [{"task_seed":secrets.token_hex(16),"secret_seed":secrets.token_hex(32)} for _ in range(cases)]
    # A cryptographic draw is independent of development; also reject accidental seed reuse.
    existing = []
    for path in (common.RESULTS/"raw").glob("*/private.json"):
        existing.append(json.loads(path.read_text()))
    for pair in seeds:
        if any(pair[k] == old.get(k) for old in existing for k in pair):
            raise ValueError("Held-out seed overlaps development evidence")
    plan = [{"index":2*i+j,"case":i,"config":{**config,"defence":policy},"seed_commitment":common.digest(pair)}
            for i,pair in enumerate(seeds) for j,policy in enumerate(("prompt_only","enforced"))]
    manifest = {"id":cid,"protocol":"v4.0.0-dev","frozen_at":common.now(),"code_sha256":common.frozen_code(),
                "identity":identity,"plan":plan,"private_seeds_sha256":common.digest(seeds),
                "scoring":"Deterministic judge.py; paired descriptive comparisons by case; invalid/incomplete retained separately.",
                "planned_calls":sum(2*p["config"]["turn_budget"]+2 for p in plan),
                "planned_cli_budget_usd":sum(p["config"]["max_cost_usd"] for p in plan)}
    common.write_new(folder/"seeds.private.json",seeds,private=True)
    common.write_new(folder/"manifest.json",manifest)
    common.write_new(folder/"seal.json",{"manifest_sha256":common.digest(manifest)})
    return folder,manifest


def verify(folder, identity=None):
    folder=Path(folder)
    m=json.loads((folder/"manifest.json").read_text())
    if json.loads((folder/"seal.json").read_text())["manifest_sha256"] != common.digest(m):
        raise ValueError("Frozen manifest changed")
    seeds=json.loads((folder/"seeds.private.json").read_text())
    if m["code_sha256"] != common.frozen_code():
        raise ValueError("Frozen protocol or source changed. Create a new campaign; do not rewrite this freeze.")
    if common.digest(seeds) != m["private_seeds_sha256"]:
        raise ValueError("Frozen seeds changed")
    actual=identity or preflight()
    if not actual.get("ready") or any(actual.get(k)!=m["identity"].get(k) for k in ("version","binary_sha256","help_sha256")):
        raise ValueError("Frozen CLI identity changed")
    for item in m["plan"]:
        if item["seed_commitment"] != common.digest(seeds[item["case"]]):
            raise ValueError("Seed plan mismatch")
        validate_config(item["config"])
    return m,seeds


def run_next(folder, opt_in=False):
    if not opt_in:
        raise ValueError("Explicit inference opt-in is required")
    folder=Path(folder)
    if not re.fullmatch(r"campaign-[a-f0-9]{16}",folder.name):
        raise ValueError("Invalid campaign directory")
    m,seeds=verify(folder)
    item=next((item for item in m["plan"] if not (folder/f"attempt-{item['index']}.json").exists()),None)
    if item is None:
        raise ValueError("Every planned episode has already been attempted")
    # Never retry an attempted episode, including a crashed process.
    common.write_new(folder/f"attempt-{item['index']}.json",{"started_at":common.now(),"item":item,"manifest_sha256":common.digest(m)})
    job=Run(item["config"],m["identity"],seeds=seeds[item["case"]],campaign={"id":m["id"],"case":item["case"],"index":item["index"],"manifest_sha256":common.digest(m)})
    result=job.execute()
    common.write_new(folder/f"result-{item['index']}.json",{"run_id":job.id,"status":result["status"]})
    return result
