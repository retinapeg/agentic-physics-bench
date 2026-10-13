"""Shortcut pass rates vs tolerance for candidate V3 strata (read-only; imports the frozen reference function)."""
import random, statistics, sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[3] / "src"))  # repo src/ (path made relative on 2026-10-13)
from tasks import ls_slope, A_MAX, V0_MIN, V0_MAX

def gen(rng, n, dt, jitter, t_dp, v_dp, sigma, sign):
    a = sign * A_MAX * (1 - rng.random()); v0 = V0_MIN + (V0_MAX - V0_MIN) * rng.random()
    times = [dt * i + rng.uniform(0, 2 * jitter) for i in range(n)]
    t = [float(f"{x:.{t_dp}f}") for x in times]
    v = [float(f"{v0 + a * x + rng.gauss(0, sigma):.{v_dp}f}") for x in times]
    return t, v

def shortcuts(t, v):
    n = len(t); a_ref = ls_slope(t, v); out = {}
    out["endpoint"] = (v[-1] - v[0]) / (t[-1] - t[0])
    h = n // 2
    out["split_halves"] = (statistics.mean(v[h:]) - statistics.mean(v[:h])) / (statistics.mean(t[h:]) - statistics.mean(t[:h]))
    idx = [round(i * (n - 1) / 9) for i in range(10)]
    out["subsample_10"] = ls_slope([t[i] for i in idx], [v[i] for i in idx])
    out["ignore_jitter"] = ls_slope([0.5 * i for i in range(n)], v)
    out["v_rounded_1dp"] = ls_slope(t, [round(x, 1) for x in v])
    out["exact_to_2dp"] = round(a_ref, 2)
    out["exact_to_3dp"] = round(a_ref, 3)
    return a_ref, out

STRATA = {"S1 easy (10, uniform, s0.5)": dict(n=10, dt=0.5, jitter=0.0, t_dp=1, v_dp=2, sigma=0.5),
          "V2 hard (40, jitter, s2)": dict(n=40, dt=0.5, jitter=0.2, t_dp=2, v_dp=2, sigma=2.0),
          "S2 cand (120, jitter, s2)": dict(n=120, dt=0.5, jitter=0.2, t_dp=2, v_dp=2, sigma=2.0),
          "S2 cand (120, jitter, s3)": dict(n=120, dt=0.5, jitter=0.2, t_dp=2, v_dp=2, sigma=3.0)}
TOLS = [0.01, 0.005, 0.003, 0.002, 0.001]
N = 4000
for name, p in STRATA.items():
    rng = random.Random(7)
    draws = []
    for i in range(N):
        t, v = gen(rng, **p, sign=-1 if i % 2 == 0 else 1)
        draws.append(shortcuts(t, v))
    print(f"\n{name}: pass rate (%) under +/-tol, {N} draws, seed 7")
    keys = list(draws[0][1].keys())
    print("  tol     " + "".join(f"{k:>15s}" for k in keys))
    for tol in TOLS:
        row = [100 * sum(abs(sc[k] - a) <= tol for a, sc in draws) / N for k in keys]
        print(f"  {tol:<7} " + "".join(f"{x:15.1f}" for x in row))
    sd = statistics.pstdev([a for a, _ in draws])
    print(f"  (SD of a_ref across draws {sd:.3f}; SD of a_ref about a_true ~ sigma/sqrt(Sxx))")