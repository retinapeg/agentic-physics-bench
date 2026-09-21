# Proposal: numerical vs analytical performance with a bounded mathematical-tool harness

Status: **PROPOSAL, awaiting Leo's research approval.** Drafted by Claude on 2026-09-21 at Leo's direction. Nothing here has been implemented or run. After approval: implement, calibrate on development problems, freeze, run, analyse, as in V1.

## Questions

1. **Numerical vs analytical:** on matched physics problems, how does numerical performance (computing a value) relate to analytical performance (deriving the expression for the same quantity)?
2. **Tool harness:** does a bounded mathematical-tool harness improve the weaker of the two capabilities without degrading the stronger?

## One concrete matched task example (problem P-example)

A **matched problem** asks for the same physical quantity twice: as a number (N-item) and as an expression (A-item).

**Physics:** a damped oscillator with displacement x(t) = A·e^(−γt)·cos(ωt). The quantity is the velocity v(t) = dx/dt.

**N-item (numerical)**
> An object's displacement is x(t) = A·exp(−γ t)·cos(ω t), with A = 0.120 m, γ = 0.80 s⁻¹ and ω = 5.0 rad/s. Find its velocity at t = 0.37 s, to 4 significant figures.
> Reply with exactly one JSON object and nothing else: `{"type": "final", "value": <number>, "units": "m/s"}`

**A-item (analytical)**
> An object's displacement is x(t) = A·exp(−γ t)·cos(ω t). Derive its velocity v(t) as an expression in `A`, `gamma`, `omega` and `t`. Use only `+ - * / **`, parentheses, `exp`, `sin`, `cos`, `sqrt` and those symbols.
> Reply with exactly one JSON object and nothing else: `{"type": "final", "expression": "<expression>"}`

**References**, checked by Claude on 2026-09-21:
- A-item: v(t) = −A·e^(−γt)·(γ·cos ωt + ω·sin ωt). Checked against central finite differences at 25 random parameter points: worst scaled error 2.8 × 10⁻¹⁰.
- N-item: v(0.37 s) = −0.409313 m/s, i.e. **−0.4093 m/s** to 4 s.f. The closed form and a central finite difference agree to 8 × 10⁻¹².

**Tool condition:** the same items, plus the tools below. The model may request a tool with `{"type": "tool", "name": ..., "arguments": {...}}`, and the harness validates and executes it (V1 pattern):
- `calculate(expression)`: evaluates a purely numerical expression in the restricted grammar and returns a float. No variables, no attribute access, and bounded length and exponent size.
- `differentiate(expression, variable)`: returns the derivative of a restricted-grammar expression as a string.

The grader's equivalence checker is **not** a model tool: answer keys never reach the model.

## Grading rubric (deterministic; binary for the primary result)

| Item | Correct if | Outcome codes |
|---|---|---|
| N-item | Parses as the JSON above; units exactly `m/s` (or the item's stated unit); \|value − ref\| ≤ 5 × 10⁻⁴ · \|ref\|, i.e. 4 significant figures | `correct`, `wrong_value`, `wrong_units`, `malformed_json`, `missing_output`, `invalid_run` |
| A-item | Parses as the JSON above. The expression parses in the restricted grammar and uses only the allowed symbols. It is numerically identical to the reference at 25 seeded random points in a stated domain (A∈[0.5, 2], γ∈[0.1, 2], ω∈[1, 10], t∈[0, 3]), with relative error ≤ 10⁻⁹ (absolute floor 10⁻¹²) | `correct`, `not_equivalent`, `parse_error`, `disallowed_symbol`, `malformed_json`, `missing_output`, `invalid_run` |

- **Matched-pair outcome** (per problem and condition): both correct / N only / A only / neither.
- **Reported:** every planned item, with complete denominators; paired direct vs tool changes per item type; tool-request rate; failure review separating model errors from harness errors. Pilot language only: no significance or ranking claims.
- **Not graded:** the derivation text. Only the final answer is scored, so grading stays deterministic.

## Proposed design and budget (small; subscription CLI only; no API keys or overage)

| | Proposal |
|---|---|
| Development | 2 matched problems (4 items) × 2 conditions = 8 episodes, used to calibrate difficulty and check tool use |
| Scored | 8 matched problems (16 items) × 2 conditions = 32 episodes |
| Problem families (candidates) | Derivative-based physics: damped-oscillator velocity and acceleration; force from a potential (quartic well; Lennard-Jones); relativistic dp/dv; motion with x(t) combining polynomial, exponential and trigonometric terms. Each has a closed-form derivative and a numerical evaluation point |
| Loop limits (tool condition) | ≤ 3 model calls and ≤ 2 tool executions per episode; turn *n* is a fresh CLI call with the task, the previous public replies and the tool results; no retries |
| Invocation cap | Development ≤ 16 and scored ≤ 64: **≤ 80 CLI calls in total**. Expected about 45 if tools are used about once per item |
| Controls | V1's enforced controls, freeze manifest, fixed counterbalanced order, and stop on invalid run or rate limit |

**The V1 lesson carried forward:** V1 hit a ceiling (24/24 correct) and the optional tool was never used (0/12). The development step therefore has an explicit gate. If both conditions are at ceiling on both item types, or tool use is 0 on development problems, Claude reports back before freezing, and harder development variants are proposed.

## Decisions for one approval

| # | Decision | Recommendation |
|---|---|---|
| P1 | Scope and counts | 2 development + 8 scored matched problems; the families above |
| P2 | Answer formats | As in the example: JSON with `value` + `units`, or `expression` |
| P3 | N-item tolerance | Relative 5 × 10⁻⁴ (4 s.f.), units required |
| P4 | A-item equivalence | 25-point seeded numerical identity test in the restricted grammar. If P6 is approved, add a symbolic `simplify(candidate − reference) == 0` cross-check. A disagreement between the two checks is reported, not resolved silently |
| P5 | Tools and limits | `calculate` + `differentiate`, **optional** (as in V1); ≤ 3 calls and ≤ 2 tool executions; no retries |
| P6 | Dependency | Install **SymPy (pinned) in a project virtual environment** for `differentiate` and the symbolic cross-check. The alternative is a stdlib-only differentiator for the restricted grammar: no install, but more new code to trust. Installing needs your explicit go-ahead |
| P7 | Budget | ≤ 80 CLI calls in total, with the development gate above |
| P8 | Primary endpoints, fixed before scoring | Per item type: correct/8 in each condition; paired changes; "degradation" = any item correct under direct but wrong under tools, reported per type |
