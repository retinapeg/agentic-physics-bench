# EXPERIMENT.md — DRAFT, NOT FROZEN

Status: draft for Leo's review. Nothing here is frozen until the "Freeze record" at the bottom is filled in and committed **before** any scored response is viewed. Every `DECIDE` is Leo's call; the "proposed" value is only a starting point.

## 1. Question (V0)

On synthetic velocity–time measurements, how does a bounded line-fit workflow compare with a direct answer for estimating signed acceleration in m/s²?

This narrower question supersedes the open-weight-vs-frontier question in WORKMODE.md for V0. A local open-weight system is optional, not required.

## 2. Task family

One family: given a table of (t [s], v [m/s]) pairs, report the signed acceleration in m/s².

- Development cases: 4 (`dev-01`…`dev-04`). Used for building and debugging. May be viewed freely.
- Scored cases: 12 (`s-01`…`s-12`). Generated from a separate seed. Not shown to any model, and their responses are not inspected, until the freeze record is committed.
- Answer keys are stored in a file separate from the prompts, outside any directory a model-run working directory can read.

## 3. Generation method

For each case: draw a true acceleration `a_true` and initial velocity `v0`; set `v_i = v0 + a_true * t_i + ε_i`, `ε_i ~ N(0, σ²)`; round `v_i` to the displayed precision.

| Parameter | Proposed | Leo's decision |
|---|---|---|
| Seed (dev / scored) | two different integers | 101 (dev) / 202 (scored) |
| Points per case N | 8–12 | 10 |
| Time grid | uniform, t = 0…(N−1)·Δt, Δt = 0.5 s | t = 0, 0.5, …, 4.5 s; the same for every case |
| `a_true` range | uniform on [−5, 5] m/s², not rounded to a "nice" value; include negative cases in both splits | Continuous in ±(0, 5] m/s², not rounded. Sign-balanced by sampling within each sign: 2 positive / 2 negative dev, 6 / 6 scored. Minimum \|a_true\| or redraw rule: DECIDE |
| `v0` range | uniform on [−10, 10] m/s | Uniform on [−10, 10] m/s (nonzero intercept allowed) |
| Noise σ | set with tolerance (section 7) | 0.5 m/s, PROVISIONAL, development only. Final value: DECIDE before freeze. At 0.5 m/s, SD(a_ref about a_true) = σ/√20.625 s² ≈ 0.11 m/s² |
| Displayed velocity precision | 2 decimals | 2 decimals; the reference is computed from exactly the displayed values |

Provenance: Leo made these decisions in chat. Claude entered them here at Leo's direction on 2026-09-21. Sxx = 20.625 s² was supplied by Codex and rechecked by Claude with python3.

Implementation: `src/tasks.py`, written by Claude at Leo's direction. It uses one `random.Random(seed)` per split and runs on Python 3.11.5.
- Draw order per case: |a_true| = 5·(1 − random()), which lies in (0, 5]; v0 = −10 + 20·random(); then one `gauss(0, σ)` per time point.
- Development sign order: dev-01 −, dev-02 +, dev-03 −, dev-04 +.
- Cases hold only the displayed strings. Keys are in a separate file.
- Development files are regenerated whenever σ changes. Scored cases are not generated until the freeze.

## 4. Reference answer

Reference = ordinary least-squares slope of the **displayed (rounded)** velocities against the displayed times:

`a_ref = Σ (t_i − t̄)(v_i − v̄) / Σ (t_i − t̄)²`, units m/s².

Not `a_true`. The model sees only the displayed table; the key must be a function of exactly that table. Sign convention: positive means velocity increases with time.

Independent check before scoring: compute `a_ref` for every case two ways (hand-written closed form and `statistics.linear_regression`), and hand-check at least one dev case, including one with negative slope.

## 5. Output protocol (application-level JSON, not native function calling)

Final answer, both conditions: `{"type": "final", "acceleration": <number>, "units": "m/s^2"}`

Accepted unit strings: `m/s^2`, `m/s²`, `m s^-2` (Leo, 2026-09-21). Anything else is a units failure.

Direct-condition prompt: `prompts/direct.txt` (approved by Leo, 2026-09-21; template SHA-256 `701dcfe4f6af1ff87680060436e8dffdc918770122a26e135f5af7d1b696e7f8`). It asks explicitly for the least-squares slope and shows only the displayed table.

Workflow tool request: `{"type": "tool", "name": "fit_line", "arguments": {...}}`. `fit_line` is the only allowlisted tool; it returns slope and intercept.

- DECIDE: does the model copy the (t, v) data into `arguments`, or does the harness inject the case data by ID? Copying tests transcription; injection does not.

Parsing: exactly one JSON object in the response; no repair, no retry on malformed output. Malformed output is recorded and scored incorrect.

## 6. Conditions and episode limits

| | Direct | Bounded workflow |
|---|---|---|
| Model turns | 1 | ≤ 2 |
| Tool calls | 0 | ≤ 1 (`fit_line` only) |
| Native CLI tools (shell, file read, web) | disabled, verified in trace | disabled, verified in trace |
| Session state | fresh per episode | fresh per episode |
| Working directory | empty temp dir, no data/keys/code | same |

Claude CLI invocation used for development episodes (`src/models.py`):
- Command: `claude --print --model claude-opus-5 --tools "" --safe-mode --strict-mcp-config --no-session-persistence --output-format stream-json --verbose`.
- The prompt goes on stdin; each episode runs in a fresh empty temporary directory.
- Effort level is the CLI default and is not pinned. DECIDE before freeze.

Second turn mechanics: DECIDE between (a) a new CLI invocation whose prompt contains the full first-turn exchange plus the tool result, or (b) resuming the CLI session. Record which, since they differ in what context the model sees.

If turn 1 of the workflow returns a final answer, the episode ends (0 tool calls). If turn 2 requests another tool, it is recorded as a limit violation and scored incorrect.

Transport failures (rate limit, timeout, CLI crash): retry policy DECIDE (proposed: at most 1 retry, every attempt logged). Final failure = missing output, scored incorrect, kept in the denominator.

## 7. Scoring

Correct iff: output parses, units accepted, and `|answer − a_ref| ≤ tol`.

Development tolerance: absolute 0.01 m/s², PROVISIONAL (Leo, 2026-09-21).

Scored tolerance rule: DECIDE — absolute, relative, or `max(abs_floor, rel·|a_ref|)`. Write the justification here, including why it is not so loose that answering `a_true` or a rounded guess passes.

Primary result per system × condition: correct / 12 (all planned cases).

Secondary: paired wins/losses/ties per case (direct vs workflow); absolute error `|answer − a_ref|` among parseable answers with accepted units, reported with that smaller denominator stated. At least two raw failures examined and classified as model error vs harness error.

## 8. Systems in scope

| System | Invocation | Identity evidence | Status |
|---|---|---|---|
| Claude Code CLI, `claude-opus-5` | subscription CLI | model ID in trace | no-tool smoke test only |
| Codex CLI, requested `gpt-6-astra` | subscription CLI | **requested only; served ID not exposed** | no-tool smoke test only |
| Local open-weight (optional) | not chosen | — | not installed |

Order: complete a valid paired run (12 cases × 2 conditions) on one system before starting the next. No paid API keys; no overage.

## 9. Known confounders and limits (declared before running)

- The two CLIs are different agent systems with different wrappers and their own instructions, whose content is unverified; any cross-system difference is a system comparison, not a raw-model comparison.
- The workflow gets up to one extra model turn and extra context. An apparent tool benefit can't be separated from the extra-turn effect.
- 12 cases is a pilot: no significance claims, no general ranking.

## 10. Freeze record (fill in, then commit before any scored run)

- Commit hash of this file:
- Seeds:
- Prompt files + SHA-256:
- Reference-check evidence (command + output):
- Tolerance and justification:
- Episode limits, retry policy, second-turn mechanics:
- Date/time frozen:
