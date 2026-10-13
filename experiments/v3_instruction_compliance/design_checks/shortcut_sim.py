"""Rerun of the EXPERIMENT_V2 section-5 shortcut simulation with the draft's proposed strata (no repo files written)."""
import random, statistics, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[3] / "src"))  # repo src/ (path made relative on 2026-10-13)
from tasks import ls_slope, A_MAX, V0_MIN, V0_MAX

def gen(rng, n, dt, jitter, t_dp, v_dp, sigma):
    sign = rng.choice((-1, 1))
    a = sign * A_MAX * (1 - rng.random()); v0 = V0_MIN + (V0_MAX - V0_MIN) * rng.random()
    times = [dt * i + rng.uniform(0, 2 * jitter) for i in range(n)]
    t = [float(f"{x:.{t_dp}f}") for x in times]
    v = [float(f"{v0 + a * x + rng.gauss(0, sigma):.{v_dp}f}") for x in times]
    return t, v

def shortcuts(t, v):
    n = len(t); a_ref = ls_slope(t, v)
    out = {}
    out["endpoint"] = (v[-1] - v[0]) / (t[-1] - t[0])
    h = n // 2
    out["split_halves"] = (statistics.mean(v[h:]) - statistics.mean(v[:h])) / (statistics.mean(t[h:]) - statistics.mean(t[:h]))
    idx = [round(i * (n - 1) / 9) for i in range(10)]
    out["subsample_10"] = ls_slope([t[i] for i in idx], [v[i] for i in idx])
    out["ignore_jitter"] = ls_slope([0.5 * i for i in range(n)], v)
    out["round_2dp"] = round(a_ref, 2)
    out["v_1dp"] = ls_slope(t, [round(x, 1) for x in v])
    return a_ref, out

for name, p in {"V2 hard (40)": dict(n=40, dt=0.5, jitter=0.2, t_dp=2, v_dp=2, sigma=2.0),
                "S2 proposed (120)": dict(n=120, dt=0.5, jitter=0.2, t_dp=2, v_dp=2, sigma=2.0),
                "S2 escalated (200)": dict(n=200, dt=0.5, jitter=0.2, t_dp=2, v_dp=2, sigma=2.0)}.items():
    rng = random.Random(7); N = 4000
    passes = {}
    ls_sd = []
    for _ in range(N):
        t, v = gen(rng, **p)
        a_ref, sc = shortcuts(t, v)
        for k, val in sc.items():
            passes[k] = passes.get(k, 0) + (abs(val - a_ref) <= 0.01)
    print(f"{name}: pass rate under +/-0.01 of a_ref, {N} draws, seed 7")
    for k, c in passes.items():
        print(f"   {k:14s} {100*c/N:5.1f}%")