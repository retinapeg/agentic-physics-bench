# Methodology and validity

This document summarises how the study was run and what it can and cannot support. The frozen protocols are the authority: [`EXPERIMENT.md`](../EXPERIMENT.md) for V1 and [`EXPERIMENT_V2.md`](../EXPERIMENT_V2.md) for V2. Numbers are checked by `python3 src/headline_results.py`, and their sources are listed in [`results/RESULTS_MANIFEST.md`](../results/RESULTS_MANIFEST.md).

## 1. Study question

When a language model can call a bounded numerical tool, does the tool policy (none, optional, required) change what it gets right? Does it choose to use the tool, and does it use the returned result faithfully? How does that change as the arithmetic gets harder?

- **V1:** on easy tasks, does an optional `fit_line` tool change correctness, and is it requested?
- **V2:** across three difficulty levels, how do no-tool, optional-tool and required-tool policies affect correctness, uptake, relay fidelity and failure modes?

## 2. System under test

- **Model and interface.** `claude-opus-5` through the Claude Code CLI in print mode, on a Claude subscription (no API key). V1 used CLI 2.1.278 and V2 used 2.1.280.
- **Call isolation.**
  - Every call runs as a fresh process in an empty temporary directory.
  - Native tools, MCP servers, customisations and session persistence are off (`--tools "" --safe-mode --strict-mcp-config --no-session-persistence`).
  - Effort is `high`, which is requested but cannot be confirmed from traces.
  - V2 also sets `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1`.
- **What is measured.** The CLI adds its own instructions, so the unit measured is the model-plus-CLI system, not the bare model.
- **The tool.** `fit_line` is a deterministic least-squares fit of the displayed table, selected by case ID. The model proposes a request as JSON text. The harness validates it against an allowlist and executes it at most once per episode. The tool never receives the answer key.

## 3. Conditions

| | Conditions | Calls per episode | Repetitions |
|---|---|---|---|
| V1 | direct answer; optional `fit_line` workflow | 1; ≤ 2 | 1 |
| V2 | no tool; optional `fit_line`; required `fit_line` | exactly 2 in every condition | 3 |

V2 gives every condition two calls, and the final answer is always the turn-2 reply. A tool effect therefore cannot be an extra-turn effect. The required condition is a diagnostic of the mechanism and relay fidelity, not a measure of voluntary tool use. If the model answers at turn 1 in that condition, the reply is recorded as noncompliance, and the episode still gets turn 2.

## 4. Tasks, splits and scoring

- **Task family.** Each task is a table of (time, velocity) readings, and the answer is the acceleration as the least-squares slope in m/s².
- **Reference answer.** The reference is the least-squares slope of exactly the displayed strings, never the generating value. Tests check it against `statistics.linear_regression` and exact fraction arithmetic.
- **Scoring.**
  - An answer is correct if it parses as exactly one JSON object with accepted units and is within ±0.01 m/s² of the reference.
  - There is no repair and no retry.
  - V2 uses the same tolerance in every difficulty group.
  - A simulation shows that named shortcuts rarely pass in the harder groups: endpoint slope, split halves, a 10-point subsample, and ignoring the time jitter (`EXPERIMENT_V2.md` section 5). That does not exclude every approximate method.
- **V2 difficulty.**

  | Group | Points | Time grid | Noise σ |
  |---|---|---|---|
  | easy | 10 | uniform | 0.5 m/s |
  | moderate | 24 | irregular | 1 m/s |
  | hard | 40 | irregular | 2 m/s |

  The easy group reuses V1's generator with a new seed.
- **Development and held-out splits.** Development and held-out tasks use different seeds and files. Held-out tasks, keys and the run plan were generated and hashed before any scored call, and no model saw them before the freeze.

  | | Development | Held-out |
  |---|---|---|
  | V1 | 4 cases (2 episodes run, on `dev-01`) | 12 cases |
  | V2 | 6 tasks | 18 tasks |

  Development results establish that the mechanism works. No statistical claim rests on them.

## 5. Trace collection

The full CLI event stream of every call is saved under `results/raw/`. It is gitignored because it contains session metadata; 447 files are kept locally.

A reviewed per-call summary goes into the committed episode records (`results/**/episodes_*.jsonl`), with paths redacted. For V2 it includes:

- the model IDs in the usage report
- server-side tool blocks
- usage iteration types
- CLI version
- token counts
- latency
- any control violation

Episode files are append-only, and neither runner repeats an attempted episode. V2 also logs each attempt before its first call, so an interrupted episode is never replayed.

## 6. Contamination detection

**What happened.** During V2 development, a multi-agent code review reading one raw trace found a server-side `advisor` tool block, and a second model, `claude-fable-5-1`, in the usage report of a call made with tools disabled. An audit of all 48 unique calls from development stages 1–2 found it in 31 calls (21 of 24 episodes). V1's controls could not see it:

| What V1's controls checked | Where the advisor appeared |
|---|---|
| native `tool_use` blocks | `server_tool_use` / `advisor_tool_result` blocks |
| each assistant message's model ID | an `advisor_message` usage iteration |
| | a second `modelUsage` entry |

**What was done.**

1. Stages 1–2 were declared void and archived verbatim with per-call audits (`results/v2/dev_stage1/`, `dev_stage2/`). A gate decision taken on them, escalating the hard group to 60 points, was reverted.
2. The advisor was disabled per call by environment variable. The setting is recorded in every episode and in the freeze manifest, and checked before a scored run. A one-call probe with the variable set showed only `claude-opus-5`.
3. Three per-call checks were added (`src/run_v2.py`, `v2_control_violations`, with regression tests): any server-side tool block, any model other than `claude-opus-5` in the usage report, or any non-message usage iteration invalidates the episode.
4. The full development plan was rerun (stage 3) under the new checks.
5. V1's 24 scored raw traces were rescanned. Assistant content is thinking and text only, and `modelUsage` lists `claude-opus-5` alone. On the available evidence V1 is unaffected.

**Re-derivation (2026-09-27).** `src/headline_results.py` recounts the audit from the committed audit files and checks them against the archived stage records. Where the raw traces are present, it re-classifies every call from its raw trace with the runner's own control logic. The results:

| Calls | Result |
|---|---|
| V2 development stages 1–2 | 31/48 with a second model; the raw traces agree with the audit files call by call |
| V2 development stages 3–4 | 48/48 with `claude-opus-5` only |
| V2 held-out | 324/324 with `claude-opus-5` only |
| V1 held-out | 24/24 with `claude-opus-5` only |

The public repository supports the 31/48 figure through the committed audit files only. The stage 1–2 episode records predate the per-call model fields, and the raw traces are not published.

This is a finding about harness controls, not about the provider's intent.

## 7. Exclusion criteria (fixed before scoring)

- **Control violations.** A call with any control violation makes its episode `invalid_run`. The episode is not graded, stays in the denominator, and stops the batch. Violations are: missing or unexpected init metadata, native tool use, MCP servers, overage, an unexpected model, stderr output, and in V2 also the CLI version, server-side tools, second models and non-message iterations.
- **Graded outcomes.** Timeouts (`missing_output`), malformed JSON, wrong units, a tool request at the final turn and refusals are graded outcomes, not exclusions.
- **Held-out runs.** V1 had 24/24 valid episodes and V2 had 162/162. Neither run had a timeout. No episode was excluded, repeated or added, and V2 reports `duplicates 0; unplanned 0`.
- **Development.** Only one prompt-wording revision was permitted, and the grader, tolerance and tasks could not change on development evidence. The recorded changes:
  - Stages 1–2: void (section 6).
  - Stage 3: the no-tool records were superseded when Leo set the explicit no-tool wording (decision V2-4b). They are kept as a finding in `results/v2/dev_stage3/`.

## 8. Provider and system failures

| Issue | How it was handled |
|---|---|
| Second model via the server-side advisor | Section 6; development only |
| CLI version drift | V1 froze 2.1.278; V2 ran on 2.1.280. V2 checks the version per call; a V1 rerun would need 2.1.278 |
| Unknown `--effort` values are not rejected | The CLI only warns on stderr and falls back to the default, so any stderr output is a violation. No scored call produced stderr |
| Effort, sampling settings and serving changes | Not observable from traces; results are dated observations of a hosted system |
| Timeouts and rate limits | 600 s per call in V2; stop on three consecutive timeouts or a rate-limit status other than allowed. None occurred in either held-out run |
| Harness defects found in review | Fixed before each freeze, with regression tests (V1: 2 defects; V2: 3, then 10 more alongside the contamination finding) |

## 9. Statistical limitations

- **Sample size.** The held-out sets are small: 12 tasks in V1 and 18 in V2. V2's three repetitions per task are clustered observations, not independent ones.
- **Paired analysis.** Condition contrasts are task-level paired differences with a seeded cluster bootstrap over tasks (2,000 resamples). Every observed difference is zero, so every interval is [0, 0]. That describes these data; it is not evidence of equivalence.
- **Ceiling effect.** Every condition was at the ceiling, so the design has no power here to detect a tool effect on correctness in either direction.
- **Scope.** The study covers one system, one task family and one date per run. The V1 → V2 comparison is not a controlled contrast: the CLI version, prompt parenthetical, turn structure, advisor setting, tasks and date all differ.
- **Development sets** (2 episodes in V1, 6 tasks in V2) support observations about mechanism and wording, not rates.

## 10. What the evidence supports

- On these tasks, `claude-opus-5` behind the Claude Code CLI returned answers within ±0.01 m/s² in every held-out episode of every condition: V1 24/24 and V2 162/162.
- Offered an optional tool in V2, it requested it every time (54/54) and relayed every executed result within tolerance (108/108). Required-tool compliance was 54/54.
- Without a tool, observed latency and CLI-reported thinking tokens per call rose with task size. With a tool, they were about 5 s and 0.
- In development, the no-tool baseline depended on prompt wording. Under the earlier wording the model repeatedly tried to run code it did not have.
- A CLI feature added a second model to calls declared tool-free. Per-call trace checks on model identity and server-side tools detect it, and controls limited to native tool blocks and message model IDs do not.

## 11. What the evidence does not support

- That tool access improves, or harms, accuracy on these tasks.
- That the model performed a full regression when unaided. The reasoning is redacted.
- That latency or reported tokens measure internal computation or cost.
- That task difficulty caused the 0/12 → 54/54 change in optional-tool uptake.
- Anything about other models, other CLIs, other task families, long-horizon behaviour, or the bare model without the CLI.
- That an LLM is needed for this task. A deterministic least-squares function scores 12/12 and 18/18.
- Anything about the provider's intent regarding the advisor.

## Architecture (V1)

![Architecture at v1.0.0: seeded synthetic cases feed a runner that calls Claude through the Claude Code CLI, directly or through a bounded fit_line loop; a deterministic grader compares answers with hidden keys, and offline scripts summarise the saved traces](images/architecture.svg)

V2 keeps this structure. It adds a two-turn loop (`src/agent_v2.py`), a runner with the added trace checks and resumable blocks (`src/run_v2.py`), and V2 analysis (`src/analyze_v2.py`). It imports V1's reference function, tool, parser, grader, CLI adapter and control checks unchanged. The V2 episode flow is diagrammed in the [README](GUIDE.md#how-an-episode-runs-v2).
