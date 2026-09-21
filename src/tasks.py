"""Synthetic velocity-time cases and their reference answers.

Written by Claude at Leo's direction (2026-09-21). Parameters follow
EXPERIMENT.md section 3, which is still DRAFT; sigma is provisional.
Scored cases (seed 202) are not generated until the protocol is frozen.

Run from the repo root to (re)write the development files:
    python3 src/tasks.py
"""
import hashlib
import json
import math
import random
import statistics
from pathlib import Path

N_POINTS = 10
DT = 0.5  # s
A_MAX = 5.0  # m/s^2; |a_true| is drawn from (0, A_MAX]
V0_MIN, V0_MAX = -10.0, 10.0  # m/s
DEV_SEED = 101
DEV_SIGNS = (-1, +1, -1, +1)  # dev-01..dev-04: two negative, two positive
SIGMA_DEV = 0.5  # m/s, PROVISIONAL (development only)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def ls_slope(t, v):
    """Least-squares slope of v against t (units of v per unit of t)."""
    if len(t) != len(v):
        raise ValueError(f"t and v have different lengths: {len(t)} != {len(v)}")
    if len(t) < 2:
        raise ValueError("need at least two points")
    for x in list(t) + list(v):
        if not math.isfinite(x):
            raise ValueError("all values must be finite")

    t_bar = statistics.mean(t)
    v_bar = statistics.mean(v)

    s_xx = sum((ti - t_bar) ** 2 for ti in t)
    if s_xx == 0:
        raise ValueError("all times are equal; slope is undefined")

    s_xy = sum((ti - t_bar) * (vi - v_bar) for ti, vi in zip(t, v))
    return float(s_xy / s_xx)


def make_case(rng, case_id, sign, sigma):
    """Return (case, key). The case is what a model sees; the key never is.

    Draw order per case: |a_true|, v0, then one noise value per time point.
    """
    a_true = sign * A_MAX * (1.0 - rng.random())  # magnitude in (0, A_MAX]
    v0 = V0_MIN + (V0_MAX - V0_MIN) * rng.random()
    times = [DT * i for i in range(N_POINTS)]
    t_shown = [f"{ti:.1f}" for ti in times]
    v_shown = [f"{v0 + a_true * ti + rng.gauss(0.0, sigma):.2f}" for ti in times]

    # The reference is computed from exactly the strings the model will see.
    a_ref = ls_slope([float(x) for x in t_shown], [float(x) for x in v_shown])

    case = {"id": case_id, "t_s": t_shown, "v_m_per_s": v_shown}
    key = {"id": case_id, "a_ref": a_ref, "units": "m/s^2",
           "a_true": a_true, "v0": v0, "sigma": sigma}
    return case, key


def make_dev_cases(seed=DEV_SEED, sigma=SIGMA_DEV):
    """Return (cases, keys) for dev-01..dev-04 from one seeded generator."""
    rng = random.Random(seed)
    pairs = [make_case(rng, f"dev-{i:02d}", sign, sigma)
             for i, sign in enumerate(DEV_SIGNS, start=1)]
    return [case for case, _ in pairs], [key for _, key in pairs]


def to_jsonl(rows):
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)
    cases, keys = make_dev_cases()
    for name, rows in (("dev_cases.jsonl", cases), ("dev_keys.jsonl", keys)):
        text = to_jsonl(rows)
        (DATA_DIR / name).write_text(text)
        print(f"{name}  sha256={hashlib.sha256(text.encode()).hexdigest()}")
    for key in keys:
        print(f"{key['id']}  a_ref={key['a_ref']:+.4f}  a_true={key['a_true']:+.4f} m/s^2")
