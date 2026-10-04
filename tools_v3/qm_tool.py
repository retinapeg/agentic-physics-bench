"""Fixed V3 computational tool. Input: one JSON object on stdin.

Operations: eigenvalues, root, expm, simplify, integrate. Complex numbers in
JSON use {"real": number, "imag": number}; outputs use the same form.
The host sets audit environment variables only for this subprocess.
"""
import ast
import datetime
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.linalg import expm
from scipy.optimize import brentq
import sympy as sp


FUNCTIONS = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp,
             "sqrt": sp.sqrt, "log": sp.log, "sinh": sp.sinh, "cosh": sp.cosh}
CONSTANTS = {"pi": sp.pi, "E": sp.E, "I": sp.I}


def expression(source, variables):
    """Parse arithmetic expressions without Python evaluation or attributes."""
    if not isinstance(source, str) or len(source) > 2000:
        raise ValueError("invalid expression")
    tree = ast.parse(source, mode="eval")
    symbols = {name: sp.Symbol(name) for name in variables}

    def walk(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return sp.sympify(node.value)
        if isinstance(node, ast.Name):
            if node.id in symbols:
                return symbols[node.id]
            if node.id in CONSTANTS:
                return CONSTANTS[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = walk(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            left, right = walk(node.left), walk(node.right)
            return {ast.Add: lambda: left + right, ast.Sub: lambda: left - right,
                    ast.Mult: lambda: left * right, ast.Div: lambda: left / right,
                    ast.Pow: lambda: left ** right}[type(node.op)]()
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS:
            if len(node.args) == 1 and not node.keywords:
                return FUNCTIONS[node.func.id](walk(node.args[0]))
        raise ValueError("unsupported expression syntax")

    return walk(tree.body)


def complex_value(value):
    if isinstance(value, dict) and set(value) == {"real", "imag"}:
        return complex(value["real"], value["imag"])
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return complex(value)
    raise ValueError("invalid complex number")


def complex_json(value):
    z = complex(value)
    return {"real": float(z.real), "imag": float(z.imag)}


def matrix(value):
    result = np.asarray([[complex_value(cell) for cell in row] for row in value], dtype=complex)
    if result.ndim != 2 or result.shape[0] != result.shape[1] or not 1 <= result.shape[0] <= 64:
        raise ValueError("expected a square matrix of size 1..64")
    if not np.isfinite(result).all():
        raise ValueError("matrix must be finite")
    return result


def compute(args):
    op = args.get("operation")
    if op == "eigenvalues":
        values = np.linalg.eigvals(matrix(args["matrix"]))
        return {"eigenvalues": [complex_json(v) for v in values]}
    if op == "root":
        x = sp.Symbol("x")
        f = sp.lambdify(x, expression(args["expression"], ["x"]), modules="numpy")
        lo, hi = map(float, args["bracket"])
        if not (math.isfinite(lo) and math.isfinite(hi) and lo < hi):
            raise ValueError("invalid root bracket")
        return {"root": float(brentq(f, lo, hi))}
    if op == "expm":
        h = matrix(args["matrix"])
        t = float(args["time"])
        if not math.isfinite(t):
            raise ValueError("time must be finite")
        u = expm(-1j * h * t)
        result = {"operator": [[complex_json(v) for v in row] for row in u]}
        if "state" in args:
            state = np.asarray([complex_value(v) for v in args["state"]], dtype=complex)
            if state.shape != (h.shape[0],):
                raise ValueError("state dimension does not match matrix")
            evolved = u @ state
            result["state"] = [complex_json(v) for v in evolved]
            result["probabilities"] = [float(abs(v)**2) for v in evolved]
        return result
    if op in ("simplify", "integrate"):
        names = args.get("variables", [])
        if not isinstance(names, list) or not all(isinstance(n, str) and n.isidentifier() for n in names):
            raise ValueError("variables must be identifier strings")
        if len(names) > 12 or len(names) != len(set(names)):
            raise ValueError("invalid variables")
        expr = expression(args["expression"], names)
        if op == "simplify":
            return {"result": str(sp.simplify(expr))}
        variable = args["variable"]
        if variable not in names:
            raise ValueError("integration variable must be declared")
        if "bounds" in args:
            lower, upper = args["bounds"]
            result = sp.integrate(expr, (sp.Symbol(variable),
                                         expression(str(lower), names), expression(str(upper), names)))
        else:
            result = sp.integrate(expr, sp.Symbol(variable))
        return {"result": str(result)}
    raise ValueError("unknown operation")


def main():
    log = os.environ.get("APB_V3_TOOL_LOG")
    episode = os.environ.get("APB_V3_EPISODE_ID")
    if not log or not episode:
        raise SystemExit("host audit configuration missing")
    args = json.load(sys.stdin)
    if not isinstance(args, dict):
        raise ValueError("tool input must be a JSON object")
    event = {"episode_id": episode, "args": args,
             "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with Path(log).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
    print(json.dumps(compute(args), sort_keys=True))


if __name__ == "__main__":
    main()
