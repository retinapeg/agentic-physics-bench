"""Seeded V3 physics questions and host-only reference keys.

Run ``python3 src/tasks_v3.py`` to write both splits. Only *_tasks.jsonl
may be copied into a model sandbox. Never mount *_keys.jsonl there.
Units are dimensionless throughout: hbar = m = 1 unless stated otherwise.
"""
import json
import math
import random
from pathlib import Path

import numpy as np
from scipy.linalg import expm
from scipy.optimize import brentq
import sympy as sp

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "v3"
SEEDS = {"dev": 31031, "heldout": 31032}
GROUPS = ("easy", "moderate", "hard")
KINDS = ("well", "expectation", "barrier", "spin", "ground", "transition",
         "normalization", "x2", "commutator", "perturbation")
# Four numerical and four symbolic development tasks; twelve of each held out.
SCHEDULE = {
    "dev": [("expectation", "easy"), ("spin", "easy"),
            ("barrier", "moderate"), ("ground", "hard"),
            ("normalization", "easy"), ("x2", "moderate"),
            ("commutator", "moderate"), ("perturbation", "hard")],
    "heldout": [(kind, GROUPS[(2*k+i) % 3]) for k, kind in enumerate(KINDS[:6]) for i in range(2)]
               + [(kind, GROUPS[i % 3]) for kind in KINDS[6:] for i in range(3)],
}
NUMERIC = set(KINDS[:6])
X = sp.Symbol("x", real=True)


def _spin_hamiltonian(n, jxy, jz, fields):
    sx = np.array([[0, 1], [1, 0]], complex)
    sy = np.array([[0, -1j], [1j, 0]], complex)
    sz = np.diag([1, -1]).astype(complex)
    eye = np.eye(2, dtype=complex)

    def op(positions):
        out = np.array([[1]], complex)
        for site in range(n):
            out = np.kron(out, positions.get(site, eye))
        return out

    h = np.zeros((2**n, 2**n), complex)
    for site in range(n - 1):
        h += jxy / 4 * (op({site: sx, site + 1: sx}) + op({site: sy, site + 1: sy}))
        h += jz / 4 * op({site: sz, site + 1: sz})
    for site, field in enumerate(fields):
        h += field / 2 * op({site: sz})
    return h


def _well_energy(depth, parity):
    # Well: V=-depth for |x|<1, zero outside; z=k*a, a=1.
    radius = math.sqrt(2 * depth)
    lo, hi = (0, math.pi / 2) if parity == "even" else (math.pi / 2, math.pi)
    lo += 1e-10
    hi = min(hi - 1e-10, radius - 1e-10)
    if hi <= lo:
        raise ValueError("no bound state in requested parity interval")
    fn = (lambda z: z * math.tan(z) - math.sqrt(radius**2 - z**2)) if parity == "even" else (
        lambda z: -z / math.tan(z) - math.sqrt(radius**2 - z**2))
    z = brentq(fn, lo, hi, xtol=1e-14)
    return z*z/2 - depth


def _oscillator_moment(n, power, omega):
    size = n + power + 2
    raising = sp.zeros(size)
    for i in range(size - 1):
        raising[i + 1, i] = sp.sqrt(i + 1)
    position = (raising + raising.T) / sp.sqrt(2 * omega)
    return sp.simplify((position**power)[n, n])


def make_case(rng, task_id, kind, group):
    """Return (public case, private key), using only displayed parameters."""
    rank = GROUPS.index(group)
    p = {}
    if kind == "well":
        p = {"depth": rng.choice([5, 7, 9, 11, 14]) + rank, "parity": "odd" if rank else "even"}
        answer = _well_energy(**p)
        question = ("For V(x)=-depth on |x|<1 and V(x)=0 elsewhere, hbar=m=1, "
                    "find the lowest bound-state energy of the stated parity. Return E to 6 decimal places.")
    elif kind == "expectation":
        p = {"system": rng.choice(["oscillator", "box"]), "n": rng.randint(1 + rank, 3 + 2*rank)}
        if p["system"] == "oscillator":
            p["omega"] = rng.choice([2, 3, 4])
            answer = (p["n"] + 0.5) / p["omega"]
            question = "For the harmonic oscillator eigenstate |n>, hbar=m=1, find <x^2>. Return 6 decimal places."
        else:
            p["length"] = rng.choice([2, 3, 4])
            answer = p["length"]**2 * (1/3 - 1/(2*p["n"]**2*math.pi**2))
            question = "For a particle in an infinite box 0<x<length in state n, find <x^2>. Return 6 decimal places."
    elif kind == "barrier":
        p = {"energy": rng.choice([2, 3, 4]), "height": rng.choice([7, 9, 11]) + rank,
             "width": rng.choice([0.6, 0.8, 1.1]) + 0.1*rank}
        e, v, width = p.values()
        answer = 1 / (1 + v*v * math.sinh(math.sqrt(2*(v-e))*width)**2 / (4*e*(v-e)))
        question = ("A particle with hbar=m=1 and incident energy below the barrier height crosses "
                    "a rectangular barrier. Use the displayed energy, height, and width. "
                    "Find transmission T to 6 significant figures.")
    elif kind == "spin":
        p = {"theta": rng.choice([0.7, 1.1, 1.7]) + rank*0.13,
             "phi": rng.choice([0.4, 0.9, 1.3]), "axis_theta": rng.choice([0.8, 1.2, 1.6]),
             "axis_phi": rng.choice([0.3, 1.0, 1.8])}
        answer = (1 + math.cos(p["theta"])*math.cos(p["axis_theta"])
                  + math.sin(p["theta"])*math.sin(p["axis_theta"])
                  * math.cos(p["phi"]-p["axis_phi"]))/2
        question = ("Start in spin |0> (+z). Apply Ry(theta), then Rz(phi). Measure spin +1 "
                    "along the direction (axis_theta, axis_phi), spherical polar angles in radians. "
                    "What is the probability? Return 6 decimal places.")
    elif kind in ("ground", "transition"):
        n = 4 + rank
        p = {"sites": n, "jxy": rng.choice([0.8, 1.1, 1.4]),
             "jz": 0 if rng.randrange(2) else rng.choice([0.8, 1.1, 1.4]),
             "fields": [round(rng.uniform(-0.7, 0.7), 2) for _ in range(n)]}
        h = _spin_hamiltonian(n, p["jxy"], p["jz"], p["fields"])
        spec = ("Open chain: H=sum_i [jxy*(X_i X_(i+1)+Y_i Y_(i+1))/4 "
                "+jz*Z_i Z_(i+1)/4]+sum_i fields[i]*Z_i/2. "
                "Sites run left to right; |0> has Z=+1. hbar=1. ")
        if kind == "ground":
            answer = float(np.linalg.eigvalsh(h)[0])
            question = spec + "Find the ground-state energy to 6 decimal places."
        else:
            # Same magnetization sector, with a genuine state change.
            first = rng.sample(range(n), 2)
            second = [first[0], rng.choice([i for i in range(n) if i not in first])]
            start = "".join("1" if i in first else "0" for i in range(n))
            target = "".join("1" if i in second else "0" for i in range(n))
            p.update({"initial": start, "final": target, "time": rng.choice([1.3, 2.1, 2.7])})
            amp = expm(-1j*h*p["time"])[int(target, 2), int(start, 2)]
            answer = float(abs(amp)**2)
            question = spec + "Starting in |initial>, what is P(final) at time time? Return 6 significant figures."
    elif kind in ("normalization", "x2"):
        p = {"power": rng.choice([0, 1, 2, 3]) + rank,
             "alpha": rng.choice([1, 2, 3])}
        a, power = sp.Integer(p["alpha"]), p["power"]
        answer = (sp.sqrt(a**(sp.Rational(2*power+1, 2)) /
                          sp.gamma(sp.Rational(2*power+1, 2))) if kind == "normalization"
                  else sp.Rational(2*power+1, 2)/a)
        question = ("On the real line let psi(x)=N*x^power*exp(-alpha*x^2/2), alpha>0, N>0. "
                    + ("Find N exactly as a SymPy expression." if kind == "normalization" else
                       "After normalization, find <x^2> exactly as a SymPy expression."))
    elif kind == "commutator":
        p = {"power": rng.randint(2 + rank, 3 + 2*rank)}
        m = p["power"]
        answer = 2*sp.I*m*sp.Symbol("hbar")*X**(m-1)*sp.Symbol("p") + m*(m-1)*sp.Symbol("hbar")**2*X**(m-2)
        question = ("With [x,p]=I*hbar, give [x^power,p^2] exactly, normal ordered "
                    "with x to the left of p. Use symbols x,p,hbar and I.")
    elif kind == "perturbation":
        p = {"n": rng.randint(1 + rank, 3 + 2*rank), "omega": rng.choice([2, 3, 4]),
             "power": 4 if rank == 0 else 6}
        answer = sp.Symbol("lam") * _oscillator_moment(p["n"], p["power"], sp.Integer(p["omega"]))
        question = ("For H0=p^2/2+omega^2*x^2/2, hbar=m=1, with V=lam*x^power, "
                    "find the first-order energy correction to level n exactly. Include lam.")
    else:
        raise ValueError(kind)
    case = {"id": task_id, "family": "numeric_qm" if kind in NUMERIC else "symbolic",
            "group": group, "kind": kind, "parameters": p, "question": question}
    symbolic_answer = sp.expand(answer) if kind == "commutator" else sp.simplify(answer)
    key = {"id": task_id, "family": case["family"], "group": group, "kind": kind,
           "answer": float(answer) if kind in NUMERIC else str(symbolic_answer),
           "answer_type": "numeric" if kind in NUMERIC else "sympy"}
    return case, key


def make_tasks(split):
    if split not in SCHEDULE:
        raise ValueError(split)
    rng = random.Random(SEEDS[split])
    cases, keys = [], []
    seen = ({(c["kind"], json.dumps(c["parameters"], sort_keys=True))
             for c in make_tasks("dev")[0]} if split == "heldout" else set())
    for i, (kind, group) in enumerate(SCHEDULE[split], 1):
        for _ in range(100):
            case, key = make_case(rng, f"{'d' if split == 'dev' else 'h'}-{i:02d}", kind, group)
            fingerprint = (kind, json.dumps(case["parameters"], sort_keys=True))
            if fingerprint not in seen and (kind != "transition" or 1e-3 < key["answer"] < 0.95):
                break
        else:
            raise ValueError(f"Could not generate distinct {split} {kind} task")
        seen.add(fingerprint)
        cases.append(case)
        keys.append(key)
    return cases, keys


def files(split):
    cases, keys = make_tasks(split)
    def jsonl(rows):
        return "".join(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in rows)
    return {f"{split}_tasks.jsonl": jsonl(cases), f"{split}_keys.jsonl": jsonl(keys)}


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for split in SCHEDULE:
        for name, body in files(split).items():
            path = DATA_DIR / name
            if path.exists():
                raise SystemExit(f"Refusing to overwrite {path}")
            path.write_text(body)
            print(path)
