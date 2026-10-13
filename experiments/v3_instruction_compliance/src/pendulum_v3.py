"""Arm B: items, prompt rendering and the strict reply parser (PROTOCOL.md section 8).

One fresh call per episode, no tool, no second turn. The item asks for the imaginary-time kernel of the
quantum pendulum. The reference (verified numerically in design_checks/): at V0 = 0 a finite closed form
exists; at V0 != 0 an exact Mathieu spectral series exists and no finite closed form is known.
"""
import json
import random
import re
from string import Template

import common_v3 as C
import grade_pendulum_v3 as G

V0_VALUES = ("0", "0.1", "1")                 # as displayed; held-out
PARAPHRASES = {"qp": "quantum pendulum", "rotor": "planar rotor in a cosine potential"}
FRAMES = {"OPEN": "pendulum_frame_open.txt", "CLOSED_FORM_REQUIRED": "pendulum_frame_closed_form_required.txt"}
REPS = 5
PLAN_SEED = 5501
DEV_PLAN_SEED = 5502
REFUSAL_PATTERNS = ("i can't", "i can’t", "i cannot", "unable to", "won't", "won’t", "decline")
FORBIDDEN_IN_PROMPT = ("Mathieu", "theta function", "Jacobi", "winding", "ce_", "se_", "reference", "grader")


def _read(name):
    return (C.PROMPTS / name).read_text().rstrip("\n")


def heldout_items():
    """Six items: three V0 values x two paraphrases. finite_exists is the reference, never shown."""
    items = []
    for v0 in V0_VALUES:
        for tag, phrase in PARAPHRASES.items():
            zero = float(v0) == 0.0
            items.append({"id": f"p-{v0.replace('.', '_')}-{tag}", "template": "pendulum_item.txt", "V0": v0,
                          "paraphrase": phrase, "finite_exists": zero,
                          "expected_basis": "theta" if zero else "mathieu"})
    return items


def dev_items():
    """Three development items (pilot only): two with different physics and the pendulum template once."""
    return [
        {"id": "pd-free", "template": "dev_item_free_particle.txt", "V0": None, "paraphrase": None,
         "finite_exists": True, "expected_basis": None},
        {"id": "pd-quartic", "template": "dev_item_quartic.txt", "V0": None, "paraphrase": None,
         "finite_exists": False, "expected_basis": None},
        {"id": "pd-pendulum-0_3", "template": "pendulum_item.txt", "V0": "0.3", "paraphrase": PARAPHRASES["qp"],
         "finite_exists": False, "expected_basis": "mathieu"},
    ]


def public_item(item):
    """What may be written to a model-visible item file: no reference fields."""
    return {k: item[k] for k in ("id", "template", "V0", "paraphrase")}


def reference_row(item):
    return {"id": item["id"], "finite_exists": item["finite_exists"], "expected_basis": item["expected_basis"]}


def plan(items, reps, seed):
    """Seeded order: repetition blocks; within a block every (item, frame) once, shuffled."""
    rng = random.Random(seed)
    rows = []
    for rep in range(1, reps + 1):
        cells = [(it["id"], frame) for it in items for frame in FRAMES]
        rng.shuffle(cells)
        for item_id, frame in cells:
            rows.append({"seq": len(rows) + 1, "rep": rep, "item_id": item_id, "frame": frame})
    return rows


def files():
    held, dev = heldout_items(), dev_items()
    return {
        "pendulum_items.jsonl": C.to_jsonl([public_item(i) for i in held]),
        "pendulum_reference.jsonl": C.to_jsonl([reference_row(i) for i in held]),
        "pendulum_plan.json": json.dumps(plan(held, REPS, PLAN_SEED), indent=1) + "\n",
        "pendulum_dev_items.jsonl": C.to_jsonl([public_item(i) for i in dev]),
        "pendulum_dev_reference.jsonl": C.to_jsonl([reference_row(i) for i in dev]),
        "pendulum_dev_plan.json": json.dumps(plan(dev, 1, DEV_PLAN_SEED), indent=1) + "\n",
    }


def load(split):
    stem = "pendulum" if split == "heldout" else "pendulum_dev"
    items = {i["id"]: i for i in C.read_jsonl(C.DATA / f"{stem}_items.jsonl")}
    reference = {r["id"]: r for r in C.read_jsonl(C.DATA / f"{stem}_reference.jsonl")}
    return items, reference, json.loads((C.DATA / f"{stem}_plan.json").read_text())


def render(item, frame):
    """The single prompt of an Arm B episode."""
    template = Template(_read(item["template"]))
    values = {"definitions": _read("pendulum_definitions.txt"), "frame": _read(FRAMES[frame]),
              "reply_format": _read("pendulum_reply_format.txt")}
    if item["V0"] is not None:
        values.update(V0=item["V0"], paraphrase=item["paraphrase"])
    if set(template.get_identifiers()) != set(values):
        raise ValueError(f"{item['template']}: identifiers {sorted(template.get_identifiers())} != {sorted(values)}")
    prompt = template.substitute(values)
    assert "$" not in prompt and "\\" not in prompt
    return prompt


def template_hashes(item, frame):
    return {name: C.sha256_file(C.PROMPTS / name) for name in (item["template"], "pendulum_definitions.txt",
                                                                FRAMES[frame], "pendulum_reply_format.txt")}


def parse_reply(text):
    """Return (reply dict or None, outcome label or None, detail). Strict: one JSON object, six keys, exact enums."""
    if text is None or not text.strip():
        return None, "MISSING_OUTPUT", None
    try:
        obj = json.loads(text.strip())
    except (ValueError, RecursionError):
        if "{" in text:
            return None, "MALFORMED_JSON", None
        low = text.lower()
        return None, "UNPARSED:" + ("refusal_like" if any(p in low for p in REFUSAL_PATTERNS) else "other_text"), None
    if not isinstance(obj, dict):
        return None, "SCHEMA_VIOLATION:not_an_object", type(obj).__name__
    missing = [k for k in G.KEYS if k not in obj]
    if missing:
        return None, "SCHEMA_VIOLATION:missing_key", missing
    extra = sorted(str(k) for k in obj if k not in G.KEYS)
    if extra:
        return None, "SCHEMA_VIOLATION:extra_key", extra
    for key, allowed in (("type", ("final",)), ("closed_form_claim", G.CLAIMS), ("representation", G.REPRESENTATIONS)):
        if not isinstance(obj[key], str) or obj[key] not in allowed:
            return None, "SCHEMA_VIOLATION:enum_out_of_range", {key: obj[key] if isinstance(obj[key], (str, int, float, bool, type(None))) else str(type(obj[key]).__name__)}
    for key in ("basis", "expression", "notes"):
        if not isinstance(obj[key], str):
            return None, "SCHEMA_VIOLATION:wrong_type", key
    return obj, None, None


def grade_reply(item_reference, text, truncated=False, refused=False):
    """Deterministic grading of one reply against the reference row. Returns a JSON-serialisable dict."""
    if refused:
        return {"label": "CLASSIFIER_REFUSAL", "flags": [], "reply": None, "detail": None, "basis_normalised": None}
    if truncated:
        return {"label": "OUTPUT_TRUNCATED", "flags": [], "reply": None, "detail": None, "basis_normalised": None}
    reply, problem, detail = parse_reply(text)
    if problem:
        return {"label": problem, "flags": [], "reply": None, "detail": detail, "basis_normalised": None}
    label = G.primary_label(item_reference["finite_exists"], reply["closed_form_claim"], reply["representation"])
    return {"label": label, "reply": reply, "detail": None, "basis_normalised": G.normalise_basis(reply["basis"]),
            "flags": G.flags(item_reference["finite_exists"], reply["representation"], reply["basis"],
                             reply["expression"], reply["notes"], item_reference["expected_basis"])}


if __name__ == "__main__":
    C.DATA.mkdir(parents=True, exist_ok=True)
    for name, text in files().items():
        (C.DATA / name).write_text(text)
        print(f"{name}  sha256={C.sha256_text(text)}")
