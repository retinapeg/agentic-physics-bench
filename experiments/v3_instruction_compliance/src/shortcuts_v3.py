"""How often cheap estimators pass the grader on freshly drawn tables (standard library only).

A shortcut "passes" when it lands within the tolerance of the exact least-squares slope of the displayed
table. The simulation uses the frozen generator itself (tasks_v3.make_case_v3), so the table in PROTOCOL.md
describes the tasks actually used. Usage: python3 .../src/shortcuts_v3.py [draws]
"""
import random
import statistics
import sys

import common_v3 as C  # noqa: F401
import tasks
import tasks_v3

ESTIMATORS = ("endpoint", "split_halves", "subsample_10", "equal_spacing", "nominal_grid", "exact_2dp", "exact_3dp")


def estimates(t, v, a_ref):
    n, h = len(t), len(t) // 2
    k = max(1, n // 10)
    span = t[-1] - t[0]
    return {
        "endpoint": (v[-1] - v[0]) / span,
        "split_halves": (statistics.fmean(v[h:]) - statistics.fmean(v[:h])) / (statistics.fmean(t[h:]) - statistics.fmean(t[:h])),
        "subsample_10": tasks.ls_slope(t[::k], v[::k]),
        "equal_spacing": tasks.ls_slope([t[0] + span * i / (n - 1) for i in range(n)], v),     # true span, spacing ignored
        "nominal_grid": tasks.ls_slope([0.5 * i for i in range(n)], v),                        # the mean gap as a grid
        "exact_2dp": round(a_ref, 2), "exact_3dp": round(a_ref, 3),
    }


def pass_rates(stratum, tolerance=tasks_v3.TOLERANCE, draws=4000, seed=7):
    rng = random.Random(seed)
    hits = dict.fromkeys(ESTIMATORS, 0)
    for i in range(draws):
        case, key = tasks_v3.make_case_v3(rng, f"sim-{i}", -1 if i % 2 else 1, stratum)
        t, v = [float(x) for x in case["t_s"]], [float(x) for x in case["v_m_per_s"]]
        for name, value in estimates(t, v, key["a_ref"]).items():
            hits[name] += abs(value - key["a_ref"]) <= tolerance
    return {name: round(100.0 * hits[name] / draws, 1) for name in ESTIMATORS}


if __name__ == "__main__":
    draws = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    print(f"pass rate (%) within +/-{tasks_v3.TOLERANCE} of the exact slope; {draws} draws, seed 7")
    for stratum in tasks_v3.STRATUM_ORDER:
        print(stratum, pass_rates(stratum, draws=draws))
