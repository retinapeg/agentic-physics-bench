# V3: instruction compliance and epistemic honesty (design stage)

**Status (2026-10-13): proposed. Not approved, not frozen, nothing run.** This directory holds a design
review and the scripts that check its mathematics and statistics. It contains no task data, prompts, runner
or results, and no model has seen any of it.

## The question

V1 and V2 asked whether a model *uses* an optional tool and found correctness at the ceiling either way.
V3 asks the question the ceiling left open: **when told not to use a tool, does the system comply, and does
it say honestly what it can and cannot compute?** Two arms:

- **Arm A, instruction compliance.** The V2 line-fit protocol with the tool described in every cell and one
  policy sentence varied: none; "Try not to use the fit_line tool."; a permission marker (allowed / not
  allowed); "Do not request or use fit_line under any circumstances." The outcome is a request for the tool
  when the policy forbids it, read from the harness record, on tasks hard enough that the tool is tempting.
- **Arm B, epistemic honesty on a physics question with a known boundary.** The imaginary-time kernel of the
  quantum pendulum, H = −½ d²/dθ² − V₀ cos θ on the circle. At V₀ = 0 a finite closed form exists (a Jacobi
  theta function). At V₀ ≠ 0 an exact spectral series in Mathieu functions exists, but no finite closed form
  is known. The outcome is whether the model claims an exact closed form where none is supported, under a
  neutral prompt and under one that asks for a closed form.

The full design, its flaws and the open decisions are in [`DESIGN_REVIEW.md`](DESIGN_REVIEW.md) (sections
0–12 and "Decisions for Leo").

## What has been verified (no model calls)

The reference physics and the sample-size reasoning were checked numerically. The scripts are in
[`design_checks/`](design_checks/); they need NumPy, SciPy, SymPy and mpmath (the rest of this repository is
standard library only, and CI does not run these). Re-run on 2026-10-13 with NumPy 1.26.0, SciPy 1.11.3,
SymPy 1.14.0, mpmath 1.3.0:

| Script | What it checks | Result on 2026-10-13 |
|---|---|---|
| `check1_mathieu.py`, `mathieu_checks.py` | Mathieu mapping a = 8E, q = −4V₀; normalisation ∫ce² = π; symmetry under q → −q; the q = 0 limit against ϑ₃ | symmetry identities hold to 4e-15; the spectral form equals the ϑ₃ form to the 10 digits printed; the trace equals Σe^{−τE} to the 8 digits printed |
| `check2_kernel.py` | pendulum energies from Mathieu characteristic values against a Fourier-basis matrix; level ordering a₀ < b₂ < a₂ < …; semigroup property of the kernel | energies agree to 2e-12 (V₀ = 1) and 1e-12 (V₀ = 10); including odd orders would be wrong by 13.5; semigroup holds to 6e-17 |
| `check3_largeV0.py` | deep-well regime: harmonic ladder, tunnelling pairs, free-particle kernel normalisation | each pendulum level appears once; the small gaps (4e-9 to 7e-3 in characteristic value at V₀ = 10) pair it with an odd-order state that is not a pendulum state |
| `check5_duru.py` | a published "exact" double-series kernel (arXiv:1911.07074, as transcribed) against the exact matrix-exponential kernel | equals the first-order Trotter product to 5e-16 at five real-time points, where it differs from the exact kernel by 4–55 %; in imaginary time, 26 % at the point tested |
| `shortcut_sim.py`, `tol_sweep.py`, `tol_sweep_irregular.py` | whether cheap estimators pass the grader on 120-point tables | 4,000 seeded draws each. On V2's jittered grid at 120 points and ±0.01: split-halves passes 89.8 %, ignoring the jitter 100 %. On a gap grid (gaps U(0.1, 0.9) s) at ±0.002: split-halves 26.7 % (σ 2) or 17.4 % (σ 3), the two spacing shortcuts 8.3 % and 4.1 %, endpoint 3.2 % |
| `check4_stats.py`, `arith.py`, `cp_bounds.py`, `stats_power_checks.py` | exact power, Clopper–Pearson bounds, episode and call counts | all four run to completion (the last takes about 2 minutes); outputs not compared line by line with the review |
| `signflip_power_ref.py` | sign-flip test power by simulation | long-running; did not finish within 4 minutes on 2026-10-13 and was not re-verified |
| `v2_parser_facts.py` | facts about V2's parser and validator that the design relies on | runs to completion against this repository's `src/` |

The only change made to the recovered scripts is that a hard-coded path to this repository's `src/` was made
relative.

## Relation to the other V3 draft

A different V3 draft is on the branch
[`v3-forbidden-tool`](https://github.com/retinapeg/agentic-physics-bench/tree/v3-forbidden-tool) (2026-10-04,
one commit, built by Codex through a task queue and marked unreviewed): four tool-policy conditions with a
sandboxed code tool, a second-turn honesty question, and quantum-mechanics and symbolic-physics tasks; an
offline synthetic rehearsal only, with six decisions open before any freeze. The design review here came two
days later and takes a narrower route (the existing `fit_line` protocol plus the pendulum arm). Neither has
been approved; which design goes forward, or how they combine, is Leo's decision. Nothing from that branch is
merged here.

## Rules for this directory

- V1 and V2 stay frozen. Nothing under `results/`, `data/`, `prompts/` or the frozen modules in `src/` is
  edited by V3 work; CI enforces this against the release tags. The tag `tool-use-study-final` marks the last
  commit of the two-experiment study.
- V3 gets its own protocol, freeze manifest, run identity, data and results, all under this directory.
- No development or scored call before Leo approves a protocol and it is hashed and frozen.

The design review was written by Claude (Claude Code) at Leo's direction; Leo decides the protocol.
