"""Offline V3 answer grading. Private keys stay on the host, outside model sandboxes.

``grade(answer, key)`` accepts a scalar answer or an object with ``answer`` and
optional ``units``. A JSON object string is also accepted. Natural units in the
current V3 tasks make every requested result unitless; absent units, ``1``, and
``dimensionless`` are accepted. Other units are reported separately.

Numeric tolerance is abs(error) <= max(absolute floor, 1e-5 * abs(reference)).
The floor is 1e-6 for six-decimal-place tasks and zero for the barrier and
transition tasks that request six significant figures. These defaults are
draft protocol choices, to freeze before any
scored inference. Symbolic grading first requires simplify(a-b) == 0; eight
seeded substitution points provide a conservative backup for identities SymPy
does not simplify. The backup is not a replacement for exact equivalence.
"""
import ast
import hashlib
import json
import math
import random

import sympy as sp

REL_TOL = 1e-5
ABS_TOL = 1e-6
SYMBOLIC_REL_TOL = 1e-10
SYMBOLIC_ABS_TOL = 1e-12
POINTS = 8
ACCEPTED_UNITS = (None, "", "1", "dimensionless")
SYMBOLS = {"x": sp.Symbol("x", real=True), "p": sp.Symbol("p"),
           "hbar": sp.Symbol("hbar"), "lam": sp.Symbol("lam")}
NAMES = {**SYMBOLS, "I": sp.I, "pi": sp.pi, "E": sp.E}
FUNCTIONS = {"sqrt": sp.sqrt, "sin": sp.sin, "cos": sp.cos,
             "exp": sp.exp, "log": sp.log, "gamma": sp.gamma}


def _expression(source):
    """Parse a small arithmetic subset of SymPy notation without eval/sympify."""
    if not isinstance(source, str) or not source.strip() or len(source) > 1024:
        raise ValueError("bad expression")
    tree = ast.parse(source.strip(), mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 256:
        raise ValueError("expression too large")

    def walk(node, depth=0):
        if depth > 32:
            raise ValueError("expression too deep")
        if isinstance(node, ast.Expression):
            return walk(node.body, depth + 1)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
            if not math.isfinite(value) or abs(value) > 1e100:
                raise ValueError("invalid number")
            return sp.Integer(value) if type(value) is int else sp.Float(value)
        if isinstance(node, ast.Name) and node.id in NAMES:
            return NAMES[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = walk(node.operand, depth + 1)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left, right = walk(node.left, depth + 1), walk(node.right, depth + 1)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                if right.is_number is not True or right.is_real is not True:
                    raise ValueError("invalid power")
                exponent = float(right)
                if not math.isfinite(exponent) or abs(exponent) > 64:
                    raise ValueError("invalid power")
                return left ** right
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FUNCTIONS and len(node.args) == 1 and not node.keywords:
                return FUNCTIONS[node.func.id](walk(node.args[0], depth + 1))
        raise ValueError("unsupported expression")

    result = walk(tree)
    if result.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
        raise ValueError("nonfinite expression")
    return result


def _numeric_backup(actual, expected):
    """Check several reproducible, nonzero points when simplification is inconclusive."""
    symbols = sorted(actual.free_symbols | expected.free_symbols, key=str)
    if any(str(s) not in SYMBOLS for s in symbols):
        return False
    digest = hashlib.sha256((str(actual) + "|" + str(expected)).encode()).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    for _ in range(POINTS):
        values = {s: rng.uniform(0.35, 2.15) for s in symbols}
        try:
            a = complex(sp.N(actual.subs(values), 16))
            b = complex(sp.N(expected.subs(values), 16))
        except (ArithmeticError, TypeError, ValueError):
            return False
        if not all(math.isfinite(v) for v in (a.real, a.imag, b.real, b.imag)):
            return False
        if abs(a - b) > max(SYMBOLIC_ABS_TOL, SYMBOLIC_REL_TOL * abs(b)):
            return False
    return True


def _result(correct, outcome, abs_error=None, method=None):
    return {"correct": correct, "outcome": outcome, "abs_error": abs_error, "method": method}


def grade(answer, key, rel_tol=REL_TOL, abs_tol=None):
    """Grade a locked first answer against a host-only V3 key.

    Bad or missing model output is an incorrect outcome. A malformed private key
    or invalid grader tolerance is a setup error and is deliberately not hidden.
    """
    if key.get("answer_type") not in ("numeric", "sympy") or "answer" not in key:
        raise ValueError("invalid private key")
    if abs_tol is None:
        abs_tol = 0.0 if key.get("kind") in ("barrier", "transition") else ABS_TOL
    if not all(isinstance(t, (int, float)) and not isinstance(t, bool)
               and math.isfinite(t) and t >= 0 for t in (rel_tol, abs_tol)):
        raise ValueError("invalid tolerance")
    if answer is None or answer == "":
        return _result(False, "missing_output")
    if isinstance(answer, str) and answer.lstrip().startswith("{"):
        try:
            answer = json.loads(answer)
        except (ValueError, RecursionError):
            return _result(False, "malformed_answer")
    units = None
    if isinstance(answer, dict):
        if "answer" not in answer or set(answer) - {"answer", "units", "type"}:
            return _result(False, "malformed_answer")
        if "type" in answer and answer["type"] != "final":
            return _result(False, "malformed_answer")
        units = answer.get("units")
        answer = answer["answer"]
    if units not in ACCEPTED_UNITS:
        return _result(False, "wrong_units")

    if key["answer_type"] == "numeric":
        if isinstance(answer, bool) or not isinstance(answer, (int, float, str)):
            return _result(False, "malformed_answer")
        try:
            value = float(answer)
            reference = float(key["answer"])
        except (ValueError, TypeError, OverflowError):
            return _result(False, "malformed_answer")
        if not math.isfinite(value):
            return _result(False, "malformed_answer")
        if not math.isfinite(reference):
            raise ValueError("invalid private key")
        error = abs(value - reference)
        correct = error <= max(abs_tol, rel_tol * abs(reference))
        return _result(correct, "correct" if correct else "wrong_value", error, "numeric")

    try:
        expected = _expression(key["answer"])
    except (ArithmeticError, SyntaxError, TypeError, ValueError, RecursionError) as exc:
        raise ValueError("invalid private key") from exc
    try:
        actual = _expression(answer)
        difference = sp.simplify(actual - expected)
        if difference == 0:
            return _result(True, "correct", None, "simplify")
        if _numeric_backup(actual, expected):
            return _result(True, "correct", None, "numeric_backup")
    except Exception:  # SymPy can raise several exception types on invalid input.
        return _result(False, "malformed_answer")
    return _result(False, "wrong_value", None, "simplify_and_numeric")
