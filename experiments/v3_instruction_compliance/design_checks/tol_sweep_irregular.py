"""Candidate S2 with a genuinely irregular grid: gaps drawn U(g_min, g_max), cumulative times. No rejection loop. Read-only."""
import random, statistics, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[3] / "src"))  # repo src/ (path made relative on 2026-10-13)
from tasks import ls_slope, A_MAX, V0_MIN, V0_MAX

def gen_gaps(rng, n, g_min, g_max, t_dp, v_dp, sigma, sign):
    a = sign * A_MAX * (1 - rng.random()); v0 = V0_MIN + (V0_MAX - V0_MIN) * rng.random()
    times = [0.0]
    for _ in range(n - 1):
        times.append(times[-1] + rng.uniform(g_min, g_max))
    t = [float(f"{x:.{t_dp}f}") for x in times]
    assert all(b > a_ for a_, b in zip(t, t[1:]))
    v = [float(f"{v0 + a * x + rng.gauss(0, sigma):.{v_dp}f}") for x in times]
    return t, v

def shortcuts(t, v):
    n = len(t); a_ref = ls_slope(t, v); out = {}
    out["endpoint"] = (v[-1] - v[0]) / (t[-1] - t[0])
    h = n // 2
    out["split_halves"] = (statistics.mean(v[h:]) - statistics.mean(v[:h])) / (statistics.mean(t[h:]) - statistics.mean(t[:h]))
    idx = [round(i * (n - 1) / 9) for i in range(10)]
    out["subsample_10"] = ls_slope([t[i] for i in idx], [v[i] for i in idx])
    out["equal_spacing"] = ls_slope([t[0] + i * (t[-1] - t[0]) / (n - 1) for i in range(n)], v)
    out["nominal_0.5grid"] = ls_slope([0.5 * i for i in range(n)], v)
    out["v_rounded_1dp"] = ls_slope(t, [round(x, 1) for x in v])
    out["exact_to_2dp"] = round(a_ref, 2)
    out["exact_to_3dp"] = round(a_ref, 3)
    return a_ref, out

N = 4000
t0 = time.time()
for name, p in {"S2-gaps (120 pts, gap U(0.1,0.9), s2)": dict(n=120, g_min=0.1, g_max=0.9, t_dp=2, v_dp=2, sigma=2.0),
                "S2-gaps (120 pts, gap U(0.1,0.9), s3)": dict(n=120, g_min=0.1, g_max=0.9, t_dp=2, v_dp=2, sigma=3.0),
                "S2-gaps (80 pts, gap U(0.1,0.9), s2)": dict(n=80, g_min=0.1, g_max=0.9, t_dp=2, v_dp=2, sigma=2.0),
                "V2-like (40 pts, gap U(0.1,0.9), s2)": dict(n=40, g_min=0.1, g_max=0.9, t_dp=2, v_dp=2, sigma=2.0)}.items():
    rng = random.Random(7); draws = []
    for i in range(N):
        t, v = gen_gaps(rng, **p, sign=-1 if i % 2 == 0 else 1)
        draws.append(shortcuts(t, v))
    print(f"\n{name}: pass rate (%) under +/-tol, {N} draws, seed 7")
    keys = list(draws[0][1].keys())
    print("  tol     " + "".join(f"{k:>15s}" for k in keys))
    for tol in [0.01, 0.005, 0.003, 0.002, 0.001]:
        row = [100 * sum(abs(sc[k] - a) <= tol for a, sc in draws) / N for k in keys]
        print(f"  {tol:<7} " + "".join(f"{x:15.1f}" for x in row))
    rng2 = random.Random(7); t, v = gen_gaps(rng2, **p, sign=-1)
    print(f"  example times: {t[:5]} ... {t[-2:]}  (span {t[-1]:.1f} s)")
print(f"\nelapsed {time.time()-t0:.1f} s")