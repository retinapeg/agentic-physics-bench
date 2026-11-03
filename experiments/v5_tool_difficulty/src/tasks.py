"""Prospectively defined computational ladder; levels are not success labels.

The reference is the historical least-squares implementation applied to the
displayed decimal strings. Seed is a task-generation seed, never an inference
seed. A hidden-input calibration is a separate family, not a fifth difficulty.
"""
import hashlib
import importlib.util
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("_apb_v5_legacy_tasks", ROOT / "src/tasks.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
ls_slope = _legacy.ls_slope

LEVELS = {
    1: {"n": 6, "tolerance": 0.01, "sigma": 0.5},
    2: {"n": 40, "tolerance": 0.001, "sigma": 2.0},
    3: {"n": 120, "tolerance": 0.0001, "sigma": 2.0},
    4: {"n": 400, "tolerance": 0.00001, "sigma": 2.0},
}


def _make_task(level, seed, namespace):
    if type(level) is not int or level not in LEVELS:
        raise ValueError("level must be an integer from 1 to 4")
    if type(seed) is not int or not 0 <= seed < 2 ** 64:
        raise ValueError("seed must be an unsigned 64-bit integer")
    p = LEVELS[level]
    # Namespace levels and families; no process-global RNG state is touched.
    rng = random.Random(f"apb-v5-{namespace}:{level}:{seed}")
    a, intercept = rng.uniform(-5, 5), rng.uniform(-10, 10)
    t = [0.0]
    for _ in range(p["n"] - 1):
        t.append(t[-1] + rng.uniform(0.1, 0.9))
    shown_t = [f"{x:.4f}" for x in t]
    shown_v = [f"{intercept + a * x + rng.gauss(0, p['sigma']):.4f}" for x in t]
    opaque_id = hashlib.sha256(f"apb-v5-case:{namespace}:{level}:{seed}".encode()).hexdigest()[:20]
    case = {"id": f"v5-L{level}-{opaque_id}", "t_s": shown_t, "v_m_per_s": shown_v}
    key = {"a_ref": ls_slope(list(map(float, shown_t)), list(map(float, shown_v))),
           "tolerance": p["tolerance"], "units": "m/s^2"}
    return {"case": case, "key": key, "level": level, "seed": seed, "family": "compute",
            "case_sha256": hashlib.sha256(json.dumps(case, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def make_task(level, seed):
    return _make_task(level, seed, "compute")


def make_necessary_task(seed):
    if type(seed) is not int or not 0 <= seed < 2 ** 64:
        raise ValueError("seed must be an unsigned 64-bit integer")
    # Calibration has independent task data; task IDs disclose neither seed nor
    # measurements. Source/seed metadata still permits exact offline replay.
    task = _make_task(1, seed, "hidden-input")
    task["family"] = "hidden_input"
    task["level"] = "calibration"
    task["seed"] = seed
    opaque_id = hashlib.sha256(f"apb-v5-calibration:{seed}".encode()).hexdigest()[:20]
    task["case"]["id"] = f"v5-hidden-{opaque_id}"
    task["case_sha256"] = hashlib.sha256(json.dumps(task["case"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return task
