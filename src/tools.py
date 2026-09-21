"""Allowlisted numerical tools for the bounded workflow.

Written by Claude at Leo's direction (2026-09-21). The model names a tool and a
case ID; the harness looks up that case's displayed measurements. Tools never
receive answer keys.
"""
import statistics

from tasks import ls_slope


def fit_line(case):
    """Least-squares line through the case's displayed measurements."""
    t = [float(x) for x in case["t_s"]]
    v = [float(x) for x in case["v_m_per_s"]]
    slope = ls_slope(t, v)
    intercept = statistics.mean(v) - slope * statistics.mean(t)
    return {"slope": slope, "slope_units": "m/s^2",
            "intercept": intercept, "intercept_units": "m/s", "n_points": len(t)}


TOOLS = {"fit_line": fit_line}


def validate_request(request, case_id):
    """Return None if the request may execute, otherwise an error code."""
    if request.get("name") not in TOOLS:
        return "unknown_tool"
    args = request.get("arguments")
    if not isinstance(args, dict) or set(args) != {"case_id"}:
        return "bad_arguments"
    if args["case_id"] != case_id:
        return "wrong_case_id"
    return None
