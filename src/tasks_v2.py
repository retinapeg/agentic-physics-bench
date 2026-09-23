"""V2 tasks: the V1 velocity-time family at three difficulty levels.

Written by Claude at Leo's direction (2026-09-23). The V1 modules are frozen and
unchanged; this module imports V1's reference function (tasks.ls_slope) and, for
the easy group, V1's exact case procedure (tasks.make_case) with a new seed.

Difficulty levers (EXPERIMENT_V2.md section 2): number of points, an irregular
(jittered) time grid, and noise. The displayed velocity precision (2 dp), the
acceleration range and the scoring rule (+/-0.01 m/s^2) are V1's in every group.

Run from the repo root to (re)write the data files:
    python3 src/tasks_v2.py           # development tasks and their plan
    python3 src/tasks_v2.py scored    # scored tasks and the execution plan (at freeze)
"""
import hashlib
import json
import random
from pathlib import Path

import tasks

GROUPS = {
    # n points; grid t_i = dt*i + U(0, 2*jitter), so times start at or after 0; displayed decimals; noise sigma (m/s)
    "easy":     {"n": 10, "dt": 0.5, "jitter": 0.0, "t_dp": 1, "v_dp": 2, "sigma": 0.5},   # = V1
    "moderate": {"n": 24, "dt": 0.5, "jitter": 0.2, "t_dp": 2, "v_dp": 2, "sigma": 1.0},
    "hard":     {"n": 40, "dt": 0.5, "jitter": 0.2, "t_dp": 2, "v_dp": 2, "sigma": 2.0},
}
GROUP_ORDER = ("easy", "moderate", "hard")
GROUP_PREFIX = {"easy": "g1", "moderate": "g2", "hard": "g3"}
PREFIX_GROUP = {v: k for k, v in GROUP_PREFIX.items()}
SEEDS = {"dev": {"easy": 1101, "moderate": 1102, "hard": 1103},
         "scored": {"easy": 2201, "moderate": 2202, "hard": 2203}}
PER_GROUP = {"dev": 2, "scored": 6}          # generating signs alternate -, +, ... within each group
CONDITIONS = ("no_tool", "optional_tool", "required_tool")
REPS = {"dev": 1, "scored": 3}
PLAN_SEEDS = {"dev": 1303, "scored": 3303}
ID_PREFIX = {"dev": "d", "scored": "g"}      # d1-01 (dev, easy) ... g3-06 (scored, hard)

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "v2"


def group_of(task_id):
    """'g2-03' or 'd2-01' -> 'moderate'. The group is encoded in the ID so cases carry no extra fields."""
    return PREFIX_GROUP["g" + task_id[1]]


def make_case_v2(rng, task_id, sign, group):
    """Return (case, key). The case has V1's schema (id, t_s, v_m_per_s); the key is never shown.

    Easy group: V1's procedure exactly (tasks.make_case). Jittered groups: draw |a_true|,
    v0, then every time offset, then one noise value per point. The reference is the
    least-squares slope of exactly the displayed strings.
    """
    p = GROUPS[group]
    if p["jitter"] == 0.0:
        assert (p["n"], p["dt"], p["t_dp"], p["v_dp"]) == (tasks.N_POINTS, tasks.DT, 1, 2)
        case, key = tasks.make_case(rng, task_id, sign, p["sigma"])
    else:
        a_true = sign * tasks.A_MAX * (1.0 - rng.random())          # magnitude in (0, A_MAX]
        v0 = tasks.V0_MIN + (tasks.V0_MAX - tasks.V0_MIN) * rng.random()
        times = [p["dt"] * i + rng.uniform(0.0, 2.0 * p["jitter"]) for i in range(p["n"])]
        t_shown = [f"{t:.{p['t_dp']}f}" for t in times]
        v_shown = [f"{v0 + a_true * t + rng.gauss(0.0, p['sigma']):.{p['v_dp']}f}" for t in times]
        t_num = [float(x) for x in t_shown]
        if any(b <= a for a, b in zip(t_num, t_num[1:])):
            raise ValueError(f"{task_id}: displayed times are not strictly increasing")  # impossible for jitter < dt/2
        a_ref = tasks.ls_slope(t_num, [float(x) for x in v_shown])
        case = {"id": task_id, "t_s": t_shown, "v_m_per_s": v_shown}
        key = {"id": task_id, "a_ref": a_ref, "units": "m/s^2", "a_true": a_true, "v0": v0, "sigma": p["sigma"]}
    key = dict(key, group=group, n_points=p["n"])
    return case, key


def make_tasks(split):
    """All tasks of one split: one seeded generator per group, signs alternating -, +."""
    cases, keys = [], []
    for group in GROUP_ORDER:
        rng = random.Random(SEEDS[split][group])
        for i in range(1, PER_GROUP[split] + 1):
            sign = -1 if i % 2 == 1 else +1
            task_id = f"{ID_PREFIX[split]}{GROUP_PREFIX[group][1]}-{i:02d}"
            case, key = make_case_v2(rng, task_id, sign, group)
            cases.append(case)
            keys.append(key)
    return cases, keys


def execution_plan(task_ids, reps, seed):
    """Seeded order: repetition blocks run one after another; within a block the tasks are
    shuffled and each task's three conditions run back to back in a shuffled order. An
    interruption therefore leaves whole blocks (or whole tasks) complete."""
    rng = random.Random(seed)
    plan = []
    for rep in range(1, reps + 1):
        order = list(task_ids)
        rng.shuffle(order)
        for task_id in order:
            conditions = list(CONDITIONS)
            rng.shuffle(conditions)
            for condition in conditions:
                plan.append({"seq": len(plan) + 1, "rep": rep, "task_id": task_id, "condition": condition})
    return plan


def make_plan(split):
    cases, _ = make_tasks(split)
    return execution_plan([c["id"] for c in cases], REPS[split], PLAN_SEEDS[split])


def files(split):
    """Exact text of the three data files for a split."""
    cases, keys = make_tasks(split)
    return {f"{split}_tasks.jsonl": tasks.to_jsonl(cases),
            f"{split}_keys.jsonl": tasks.to_jsonl(keys),
            f"{split}_plan.json": json.dumps(make_plan(split), indent=1) + "\n"}


if __name__ == "__main__":
    import sys
    split = "scored" if sys.argv[1:] == ["scored"] else "dev"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in files(split).items():
        (DATA_DIR / name).write_text(text)
        print(f"{name}  sha256={hashlib.sha256(text.encode()).hexdigest()}")
    for key in make_tasks(split)[1]:
        print(f"{key['id']}  {key['group']:8s} n={key['n_points']:2d}  a_ref={key['a_ref']:+.4f}  a_true={key['a_true']:+.4f} m/s^2")
