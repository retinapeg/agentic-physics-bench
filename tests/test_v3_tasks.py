"""Independent checks of every V3 task family; no model calls."""
import json
import math
import sys
import unittest
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.optimize import root_scalar
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import tasks_v3  # noqa: E402


def independent_chain(p):
    """Build H by bit flips and Z eigenvalues, rather than Kronecker products."""
    n = p["sites"]
    h = np.zeros((2**n, 2**n), complex)
    for state in range(2**n):
        bits = [(state >> (n-1-i)) & 1 for i in range(n)]
        z = [1-2*b for b in bits]
        h[state, state] += sum(f*v/2 for f, v in zip(p["fields"], z))
        for i in range(n-1):
            h[state, state] += p["jz"]*z[i]*z[i+1]/4
            if bits[i] != bits[i+1]:
                h[state ^ (3 << (n-2-i)), state] += p["jxy"]/2
    return h


def independent_answer(case):
    p, kind = case["parameters"], case["kind"]
    if kind == "well":
        depth = p["depth"]
        # Match logarithmic derivatives, solving directly for negative E.
        def match(e):
            k, decay = math.sqrt(2*(e+depth)), math.sqrt(-2*e)
            return (k*math.tan(k)-decay if p["parity"] == "even"
                    else k/math.tan(k)+decay)
        edge = math.pi/2 if p["parity"] == "even" else math.pi
        upper = min(-1e-10, edge**2/2-depth-1e-10)
        lower = -depth + (1e-10 if p["parity"] == "even" else math.pi**2/8+1e-10)
        return root_scalar(match, bracket=(lower, upper), method="brentq", xtol=1e-13).root
    if kind == "expectation":
        n = p["n"]
        if p["system"] == "oscillator":
            # Ladder action: x|n> = sqrt((n+1)/2w)|n+1> + sqrt(n/2w)|n-1>.
            return ((n+1)+n)/(2*p["omega"])
        length = p["length"]
        x = sp.Symbol("x", real=True)
        density = 2/sp.Integer(length)*sp.sin(n*sp.pi*x/length)**2
        return float(sp.integrate(x*x*density, (x, 0, length)))
    if kind == "barrier":
        e, v, width = p["energy"], p["height"], p["width"]
        k, q = math.sqrt(2*e), math.sqrt(2*(v-e))
        # Inverse transmission amplitude from continuity at both interfaces.
        inverse_amp = math.cosh(q*width) + 1j*(q*q-k*k)/(2*k*q)*math.sinh(q*width)
        return 1/abs(inverse_amp)**2
    if kind == "spin":
        theta, phi = p["theta"], p["phi"]
        ry = np.array([[math.cos(theta/2), -math.sin(theta/2)],
                       [math.sin(theta/2), math.cos(theta/2)]], complex)
        rz = np.diag([np.exp(-0.5j*phi), np.exp(0.5j*phi)])
        state = rz @ ry @ np.array([1, 0])
        a, b = p["axis_theta"], p["axis_phi"]
        plus = np.array([math.cos(a/2), np.exp(1j*b)*math.sin(a/2)])
        return float(abs(np.vdot(plus, state))**2)
    if kind in ("ground", "transition"):
        values, vectors = np.linalg.eigh(independent_chain(p))
        if kind == "ground":
            return values[0]
        start, end = int(p["initial"], 2), int(p["final"], 2)
        amp = sum(vectors[end, j]*vectors[start, j].conjugate()
                  * np.exp(-1j*values[j]*p["time"]) for j in range(len(values)))
        return abs(amp)**2
    x = sp.Symbol("x")
    if kind in ("normalization", "x2"):
        a, power = p["alpha"], p["power"]
        norm2 = sp.integrate(x**(2*power)*sp.exp(-a*x*x), (x, -sp.oo, sp.oo))
        if kind == "normalization":
            return sp.sqrt(1/norm2)
        return sp.integrate(x**(2*power+2)*sp.exp(-a*x*x), (x, -sp.oo, sp.oo))/norm2
    if kind == "perturbation":
        n, omega, power = p["n"], sp.Integer(p["omega"]), p["power"]
        if power == 4:
            moment = 3*(2*n*n+2*n+1)/(4*omega**2)
        else:
            moment = (20*n**3+30*n*n+40*n+15)/(8*omega**3)
        return sp.Symbol("lam")*moment
    raise AssertionError(kind)


class V3TaskTests(unittest.TestCase):
    def test_counts_determinism_and_separation(self):
        for split, count in (("dev", 8), ("heldout", 24)):
            cases, keys = tasks_v3.make_tasks(split)
            self.assertEqual((cases, keys), tasks_v3.make_tasks(split))
            self.assertEqual(len(cases), count)
            self.assertEqual(len(keys), count)
            self.assertEqual({c["id"] for c in cases}, {k["id"] for k in keys})
            self.assertEqual(Counter(c["family"] for c in cases),
                             {"numeric_qm": count//2, "symbolic": count//2})
            self.assertEqual(set(c["group"] for c in cases), set(tasks_v3.GROUPS))
            for case, key in zip(cases, keys):
                self.assertEqual(case["id"], key["id"])
                self.assertNotIn("answer", case)
                self.assertNotIn("reference", case)
        dev, _ = tasks_v3.make_tasks("dev")
        held, _ = tasks_v3.make_tasks("heldout")
        self.assertFalse({c["id"] for c in dev} & {c["id"] for c in held})
        fingerprint = lambda c: (c["kind"], json.dumps(c["parameters"], sort_keys=True))
        self.assertFalse({fingerprint(c) for c in dev} & {fingerprint(c) for c in held})
        self.assertEqual(set(c["kind"] for c in dev+held), set(tasks_v3.KINDS))
        self.assertEqual(Counter(c["group"] for c in held), {g: 8 for g in tasks_v3.GROUPS})

    def test_numeric_against_independent_methods(self):
        seen = set()
        for split in tasks_v3.SCHEDULE:
            for case, key in zip(*tasks_v3.make_tasks(split)):
                if key["answer_type"] != "numeric":
                    continue
                seen.add(case["kind"])
                actual = independent_answer(case)
                self.assertTrue(np.isfinite(key["answer"]))
                self.assertAlmostEqual(key["answer"], actual, delta=2e-10, msg=case["id"])
                if case["kind"] in ("spin", "barrier", "transition"):
                    self.assertGreaterEqual(key["answer"], 0)
                    self.assertLessEqual(key["answer"], 1)
        self.assertEqual(seen, set(tasks_v3.KINDS[:6]))

    def test_symbolic_against_independent_methods(self):
        seen = set()
        x, hbar = sp.symbols("x hbar")
        for split in tasks_v3.SCHEDULE:
            for case, key in zip(*tasks_v3.make_tasks(split)):
                if key["answer_type"] != "sympy":
                    continue
                kind, p = case["kind"], case["parameters"]
                seen.add(kind)
                parsed = sp.sympify(key["answer"], locals={"x": x, "hbar": hbar})
                if kind == "commutator":
                    f = 1+x+x**3
                    m = p["power"]
                    momentum = lambda g: -sp.I*hbar*sp.diff(g, x)
                    lhs = x**m*momentum(momentum(f))-momentum(momentum(x**m*f))
                    rhs = (2*sp.I*hbar*m*x**(m-1)*momentum(f)
                           +hbar**2*m*(m-1)*x**(m-2)*f)
                    self.assertEqual(sp.simplify(lhs-rhs), 0, case["id"])
                    expected = (2*sp.I*hbar*m*x**(m-1)*sp.Symbol("p")
                                +hbar**2*m*(m-1)*x**(m-2))
                else:
                    expected = independent_answer(case)
                self.assertEqual(sp.simplify(parsed-expected), 0, case["id"])
        self.assertEqual(seen, set(tasks_v3.KINDS[6:]))

    def test_saved_files_match_and_keys_are_separate(self):
        for split in tasks_v3.SCHEDULE:
            generated = tasks_v3.files(split)
            for name, body in generated.items():
                self.assertEqual((tasks_v3.DATA_DIR/name).read_text(), body)
            questions = [json.loads(line) for line in generated[f"{split}_tasks.jsonl"].splitlines()]
            keys = [json.loads(line) for line in generated[f"{split}_keys.jsonl"].splitlines()]
            self.assertEqual([q["id"] for q in questions], [k["id"] for k in keys])
            self.assertTrue(all("answer" not in q for q in questions))


if __name__ == "__main__":
    unittest.main()
