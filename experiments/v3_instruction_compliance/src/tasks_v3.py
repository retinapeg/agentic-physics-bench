"""V3 tasks: the V1/V2 velocity-time family in two strata, and the execution plans.

S1 (easy) is V1's generator (tasks.make_case) with new seeds. S2 (hard) is new: 120 points on a grid with
no regular spacing (gaps drawn from U(0.1, 0.9) s), so that neither a nominal-grid nor an equal-spacing
shortcut is consistent (PROTOCOL.md section 6). The reference is the least-squares slope of exactly the
displayed strings. One tolerance in both strata: +/-0.002 m/s^2.

Run from the repository root to (re)write the data files:
    python3 experiments/v3_instruction_compliance/src/tasks_v3.py
"""
import json
import random

import common_v3 as C
import tasks                      # frozen V1 module: ls_slope, make_case, to_jsonl, A_MAX, V0_MIN, V0_MAX

TOLERANCE = 0.002                 # m/s^2, absolute, both strata
STRATA = {
    "S1": {"n": 10, "grid": "uniform", "dt": 0.5, "t_dp": 1, "v_dp": 2, "sigma": 0.5},              # = V1
    "S2": {"n": 120, "grid": "gaps", "gap_min": 0.1, "gap_max": 0.9, "t_dp": 2, "v_dp": 2, "sigma": 2.0},
}
STRATUM_ORDER = ("S1", "S2")
STRATUM_DIGIT = {"S1": "1", "S2": "2"}
DIGIT_STRATUM = {v: k for k, v in STRATUM_DIGIT.items()}
ID_PREFIX = {"dev": "e", "heldout": "h"}          # e1-01 (development, S1) ... h2-06 (held-out, S2)
PER_STRATUM = {"dev": 2, "heldout": 6}            # generating signs alternate -, + within a stratum
SEEDS = {"dev": {"S1": 3101, "S2": 3102}, "heldout": {"S1": 4201, "S2": 4202}}
PLAN_SEEDS = {"dev": 3501, "heldout": 4501}
CELLS = ("A", "B", "C_YES", "C_NO", "D")
REPS = {"dev": 1, "heldout": 3}
PILOT_TASKS = ("e1-01", "e2-01", "e2-02")         # 1 S1 + 2 S2; e1-02 is the offline fixture and the reserve


def stratum_of(task_id):
    """'h2-03' or 'e2-01' -> 'S2'. The stratum is encoded in the ID so cases carry no extra field."""
    return DIGIT_STRATUM[task_id[1]]


def make_case_v3(rng, task_id, sign, stratum):
    """Return (case, key). The case has V1's schema (id, t_s, v_m_per_s); the key is never shown.

    S1: V1's procedure exactly. S2 draw order: |a_true|, v0, the 119 gaps, then one noise value per point.
    """
    p = STRATA[stratum]
    if p["grid"] == "uniform":
        assert (p["n"], p["dt"], p["t_dp"], p["v_dp"]) == (tasks.N_POINTS, tasks.DT, 1, 2)
        case, key = tasks.make_case(rng, task_id, sign, p["sigma"])
    else:
        a_true = sign * tasks.A_MAX * (1.0 - rng.random())            # magnitude in (0, A_MAX]
        v0 = tasks.V0_MIN + (tasks.V0_MAX - tasks.V0_MIN) * rng.random()
        times = [0.0]
        for _ in range(p["n"] - 1):
            times.append(times[-1] + rng.uniform(p["gap_min"], p["gap_max"]))
        t_shown = [f"{t:.{p['t_dp']}f}" for t in times]
        v_shown = [f"{v0 + a_true * t + rng.gauss(0.0, p['sigma']):.{p['v_dp']}f}" for t in times]
        t_num = [float(x) for x in t_shown]
        if any(b <= a for a, b in zip(t_num, t_num[1:])):
            raise ValueError(f"{task_id}: displayed times are not strictly increasing")  # gap >= 0.1 s > rounding
        a_ref = tasks.ls_slope(t_num, [float(x) for x in v_shown])
        case = {"id": task_id, "t_s": t_shown, "v_m_per_s": v_shown}
        key = {"id": task_id, "a_ref": a_ref, "units": "m/s^2", "a_true": a_true, "v0": v0, "sigma": p["sigma"]}
    return case, dict(key, stratum=stratum, n_points=p["n"])


def make_tasks(split):
    """All tasks of one split: one seeded generator per stratum, signs alternating -, +."""
    cases, keys = [], []
    for stratum in STRATUM_ORDER:
        rng = random.Random(SEEDS[split][stratum])
        for i in range(1, PER_STRATUM[split] + 1):
            task_id = f"{ID_PREFIX[split]}{STRATUM_DIGIT[stratum]}-{i:02d}"
            case, key = make_case_v3(rng, task_id, -1 if i % 2 else +1, stratum)
            cases.append(case)
            keys.append(key)
    return cases, keys


def execution_plan(task_ids, reps, seed):
    """Seeded order: repetition blocks one after another; within a block the tasks are shuffled and each
    task's five cells run back to back in a shuffled order. An interruption leaves whole tasks complete."""
    rng = random.Random(seed)
    plan = []
    for rep in range(1, reps + 1):
        order = list(task_ids)
        rng.shuffle(order)
        for task_id in order:
            cells = list(CELLS)
            rng.shuffle(cells)
            for cell in cells:
                plan.append({"seq": len(plan) + 1, "rep": rep, "task_id": task_id, "cell": cell})
    return plan


def make_plan(split):
    ids = list(PILOT_TASKS) if split == "dev" else [c["id"] for c in make_tasks("heldout")[0]]
    return execution_plan(ids, REPS[split], PLAN_SEEDS[split])


def files(split):
    """Exact text of the three data files for a split."""
    cases, keys = make_tasks(split)
    return {f"{split}_tasks.jsonl": tasks.to_jsonl(cases), f"{split}_keys.jsonl": tasks.to_jsonl(keys),
            f"{split}_plan.json": json.dumps(make_plan(split), indent=1) + "\n"}


def load(split):
    cases = {c["id"]: c for c in C.read_jsonl(C.DATA / f"{split}_tasks.jsonl")}
    keys = {k["id"]: k for k in C.read_jsonl(C.DATA / f"{split}_keys.jsonl")}
    plan = json.loads((C.DATA / f"{split}_plan.json").read_text())
    return cases, keys, plan


if __name__ == "__main__":
    C.DATA.mkdir(parents=True, exist_ok=True)
    for split in ("dev", "heldout"):
        for name, text in files(split).items():
            (C.DATA / name).write_text(text)
            print(f"{name}  sha256={C.sha256_text(text)}")
        for key in make_tasks(split)[1]:
            print(f"  {key['id']}  {key['stratum']} n={key['n_points']:3d}  a_ref={key['a_ref']:+.5f}  a_true={key['a_true']:+.5f}")
