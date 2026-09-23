# Agentic Physics Bench

A small, fully reproducible evaluation of LLM tool use on numerical physics tasks. The system under test is a frontier model behind a coding CLI (Claude Code, `claude-opus-5`), with native tools switched off and one custom, allowlisted numerical tool dispatched by a Python harness. Every episode is saved, every count is recomputed from the saved episodes, and the protocol is frozen and hashed before any scored call.

**Status (2026-09-23).** V1 is released as tag `v1.0.0` and was re-verified in an isolated checkout. V2 (task difficulty × tool policy) is implemented, tested (90 offline checks) and calibrated on development tasks; its 162-episode scored run waits for protocol approval (`EXPERIMENT_V2.md` section 11). **No number on this page comes from a scored V2 episode.**

## Five-minute view

| | V1 (released, verified) | V2 (implementation milestone) |
|---|---|---|
| Question | On easy velocity–time tasks, does a bounded line-fit tool workflow beat a direct answer? | As the same tasks get harder, how do optional versus required tool workflows affect correctness, tool uptake and failure modes? |
| Tasks | 12 held-out cases: 10 points, uniform 0.5 s grid, σ = 0.5 m/s | 18 held-out tasks in three groups: 10 / 24 / 40 points; uniform / irregular / irregular grid; σ = 0.5 / 1.0 / 2.0 m/s |
| Conditions | direct (1 call); optional `fit_line` (≤ 2 calls) | no tool / optional tool / required tool, **2 calls in every condition**, ≤ 1 tool execution |
| Scoring | ±0.01 m/s² of the least-squares slope of the displayed data, units required | the same rule in every group |
| Result | **12/12 and 12/12 correct; the optional tool was requested 0/12 times** | development check below; scored run pending |
| Evidence | `results/episodes_scored.jsonl`, `results/summary.md`, `results/chart.svg` | `results/v2/episodes_dev.jsonl`, `results/v2/summary_dev.md`, `results/v2/chart_dev.svg` |

## The question, and why V2 exists

V1 asked one narrow question and got a boundary answer: on 12 easy held-out tasks the tool-enabled system returned correct answers without ever requesting the optional tool, and both conditions reached the scoring ceiling. That observation is kept exactly as observed. It does **not** show that tools were used, that tools are useless, that the model could not use them, or that it deliberately declined them; the explanation is the open question.

V2 separates four things V1 could not, and adds difficulty as the moving variable:

1. Does the tool mechanism work live? (the *required-tool* condition)
2. Does using the tool improve correctness? (required vs no tool, on tasks where the no-tool answer starts to fail)
3. Does the model elect to request it? (the *optional-tool* condition, by difficulty group)
4. Can it use a returned result correctly? (relay fidelity: final answer vs the tool's slope)

---

## V1: numerical physics tool-use pilot (release `v1.0.0`)

> Release naming: the development log calls this pilot "V0". Leo named the finished release **V1** (git tag `v1.0.0`) on 2026-09-21. Earlier log entries keep their original wording.

**Question.** On synthetic velocity–time measurements, how does a bounded line-fit tool workflow compare with a direct answer for estimating signed acceleration? System: Claude (`claude-opus-5`) through Claude Code CLI 2.1.278, on 12 held-out cases. A pilot: no significance claims, no model ranking.

### Result

| Condition | Correct (±0.01 m/s², units required) | Tool requested | Model calls | Median / max \|error\| (m/s²) |
|---|---|---|---|---|
| Direct answer | **12/12** | — | 12 | 1.1 × 10⁻⁴ / 4.5 × 10⁻⁴ |
| Bounded tool workflow (optional `fit_line`) | **12/12** | **0/12** | 12 | 2.1 × 10⁻⁴ / 1.5 × 10⁻³ |
| Deterministic least-squares solver (reference point) | 12/12 | — | — | 0 |

- **Paired comparison:** 12 ties. All 24 planned episodes were attempted and valid: no invalid runs, missing outputs or retries; 24 invocations against a cap of 36.
- **Answers:** every answer equals the reference slope rounded to between 1 and 6 decimals (24/24).
- **Hidden reasoning:** the CLI reported a median of about 480 output tokens per one-line answer, which includes hidden reasoning; the thinking blocks in the traces are redacted, so the model's reasoning about the tool is unrecoverable.

![Absolute error per scored case](results/chart.svg)

Table view: [`results/summary.md`](results/summary.md). Computed by [`src/analyze.py`](src/analyze.py) from [`results/episodes_scored.jsonl`](results/episodes_scored.jsonl).

**What this shows:** on this task the system reproduced the least-squares slope to within rounding in both conditions, and, given an optional tool, never used it, so both conditions sat at the ceiling.
**What it does not show:** any effect of tool access (the tool was never exercised in a scored episode); anything about other models, tasks or harder problems; that a language model is needed (an ordinary least-squares function solves the task exactly).

### Failure review

- **Model errors in scored episodes: none.** The closest case is s-07 in the workflow condition: −3.6 against a reference of −3.601455 (error 1.5 × 10⁻³), consistent with rounding to 2 decimals.
- **Harness errors, found in review before scoring and reproduced independently by Codex:** a tool request with `"name": []` crashed validation with a TypeError; the runner could record a failed control alongside a correct grade. Both were fixed before the freeze; regression tests fail on the old code and pass on the fix (`tests/test_agent.py`, `tests/test_controls.py`).
- **Configuration hazard:** the CLI does not reject an unknown `--effort` value (stderr warning, default used, model still called), so the runner treats any stderr output as a control violation. No scored call produced stderr output.

### Method (summary; full protocol in [`EXPERIMENT.md`](EXPERIMENT.md))

- 10 points at t = 0, 0.5, …, 4.5 s; noise σ = 0.5 m/s; velocities shown to 2 decimals; `a_true` continuous in ±(0, 5] m/s², 6/6 sign balance. The reference is the least-squares slope of exactly the displayed numbers, checked against `statistics.linear_regression` and exact fraction arithmetic.
- *Direct:* one call, strict JSON. *Workflow:* the model may request `fit_line` by case ID; the harness validates the request and supplies that case's displayed data, never the key; a fresh second call gets the task, the previous reply and the tool result. At most 2 calls and 1 execution, no retries.
- Controls enforced per call: no native tools or MCP servers, safe mode, empty temporary working directory, the expected model ID, no tool use, no overage, no stderr. Any violation invalidates the episode and stops the batch. The frozen files' hashes and the CLI version are checked once before the batch (`verify_freeze` in `src/run.py`).
- Freeze: protocol, prompts, data, code hashes and run order were committed and tagged `v0-protocol-freeze` before any scored call ([`data/freeze_manifest.json`](data/freeze_manifest.json)).

### Limitations

12 cases and one system. The CLI adds its own instructions, which were not verified: results describe that system, not the bare model. `fit_line` returns exactly the reference, so tool use plus faithful copying would guarantee a correct answer; the optional wording let the model skip it. The effort setting can't be confirmed from traces, only the absence of the fallback warning. The CLI's reported input-token totals don't track prompt length. The prompts were fixed after two development episodes on dev-01.

### V1 re-verification (2026-09-23)

Run by Claude at Leo's direction in an isolated `git worktree` of `v1.0.0`, without rerunning any historical episode (a rerun would be a new observation, not a replacement):

- all 36 offline checks pass; regenerating the data, analysis and chart leaves every committed file unchanged; all 14 freeze-manifest hashes match;
- every count above was recomputed from the saved episodes: 24 unique episodes in the frozen plan order, 24 valid, 0 control violations, 24 calls, 0 tool requests, 12/12 per condition; regrading every saved reply against the key file reproduces every saved grade; no prompt contains any key value;
- the workflow prompt offered the tool explicitly with the exact request JSON, and the dispatch branch was driven end to end with scripted replies: a valid request reaches `fit_line` and its result reaches the second turn's prompt verbatim;
- the one present-day limitation is the installed CLI, 2.1.280 versus the frozen 2.1.278, so `verify_freeze` now refuses a V1 scored rerun. That does not affect any V1 result.

**Verdict: V1 is complete.** Details: `RESEARCH_LOG.md`, entry "2026-09-23 | V1 verification".

---

## V2: task difficulty × tool policy (branch `v2/tool-policy`; implementation milestone)

Protocol draft: [`EXPERIMENT_V2.md`](EXPERIMENT_V2.md). Code: `src/tasks_v2.py`, `src/agent_v2.py`, `src/run_v2.py`, `src/analyze_v2.py`, `src/chart_v2.py`, `prompts/v2/`, `data/v2/`. V1's frozen files are untouched: V2 imports V1's reference function, tool, parser, grader, CLI adapter and control checks.

### What changed from V1, and why

| | V1 | V2 | Why |
|---|---|---|---|
| Difficulty | one group | easy = V1's generator with a new seed; moderate = 24 points on an irregular grid (t = 0.5·i + U(0, 0.4) s), σ 1.0; hard = 40 points, irregular, σ 2.0 | make the no-tool answer fail for a reason other than an arbitrary tolerance: more arithmetic, no symmetric-grid shortcut, more noise |
| Tolerance | ±0.01 m/s² | ±0.01 m/s², every group | same rule, harder data; a simulation shows the cheap shortcuts still fail in every group (`EXPERIMENT_V2.md` section 5) |
| Conditions | direct (1 call) vs optional tool (≤ 2 calls) | no tool, optional tool, required tool; **2 calls each** | the no-tool control gets the same chance to revise, so a tool effect is not confounded with an extra turn; the required condition tests the mechanism and relay fidelity |
| Repetitions | 1 | 3 | within-task variation; task-level paired analysis with a cluster bootstrap over tasks |
| Plan | fixed alternation | seeded blocks: tasks shuffled, each task's three conditions back to back in shuffled order | interruption leaves whole blocks complete; resume never repeats an episode |
| CLI | 2.1.278, 180 s timeout | 2.1.280, 600 s timeout, server-side advisor disabled | the installed version; harder tasks may think for minutes; the advisor would change the system under test |
| Controls per call | tool list, MCP list, model ID, native tool use, overage, stderr | the same, plus the CLI version and **no server-side tool, no second model in the usage report, no non-message iteration** | found necessary in development (below) |

V2 is not a replication of V1. The easy group is the closest point of comparison.

### Development check (18 episodes, 36 calls; not scored)

Stage 3 is the clean development run (18 episodes, 36 calls; CLI 2.1.280, `claude-opus-5`, effort high, the CLI's server-side advisor disabled, controls enforced per call). Two earlier stages are archived as superseded because a server-side "advisor" had consulted `claude-fable-5-1` inside 31 of their 48 calls (`results/v2/dev_stage1/`, `dev_stage2/`; see "What the development check taught us" below).

![Development results: proportion correct by group and condition](results/v2/chart_dev.svg)

| Group (points) | No tool | Optional tool (requested / executed) | Required tool (compliant) |
|---|---|---|---|
| easy (10) | 2/2 | 2/2 (2 / 2) | 2/2 (2/2) |
| moderate (24) | 1/2 | 2/2 (2 / 2) | 2/2 (2/2) |
| hard (40) | 0/2 | 2/2 (2 / 2) | 2/2 (2/2) |

Table view with errors, latency, thinking tokens and the failure taxonomy: [`results/v2/summary_dev.md`](results/v2/summary_dev.md).

- **Without the tool, difficulty bites.** Every moderate and hard turn-1 reply was an attempt to run code the system does not have (a fenced bash block or tool-call syntax), and the turn-2 numbers were then outside tolerance on 3 of 4 (errors 0.014, 0.050 and 0.109 m/s²).
- **With the tool available, it was used.** The optional tool was requested at turn 1 in 6/6 episodes, with no recorded thinking tokens, and the returned slope was relayed exactly every time; required-tool compliance was 6/6.
- **Paired, task-level:** tool − no tool = +0.50 (3 of 6 tasks favour the tool, 3 tied; cluster-bootstrap interval [+0.17, +0.83] over six development tasks). This is calibration on two tasks per group, not a result; the escalation clause did not fire, so the hard group stays at 40 points.

**What the development check taught us.** The first two development stages looked like a ceiling (18/18 correct, tool requested 3/6 when optional), in line with V1. The independent review then found, in one raw trace, a server-side `advisor` tool that had consulted `claude-fable-5-1` inside a call made with `--tools ""`; an audit found it in 31 of 48 calls. V1's controls check the CLI's tool list and each assistant message's model, neither of which shows a server-side tool or a second model in the usage report. V1's own 24 scored traces show only `claude-opus-5`, so V1 stands. V2 now disables the advisor by environment variable, records that in every episode and the manifest, and invalidates any call that reports a server-side tool, a second model or a non-message iteration. With the advisor off, the same tasks stopped being easy: the difficulty gradient and the tool effect above only appeared once the evaluated system was actually the declared model. It also means the V1 vs V2 tool-request rates (0/12 vs 6/6 optional requests, 2/2 on easy tasks) are **not attributable**: the CLI version, the two-turn design, one prompt sentence and the advisor state all differ.

### Scored run: pending approval

18 tasks × 3 conditions × 3 repetitions = 162 episodes, exactly 2 calls each = 324 calls, one system. It runs only after Leo approves decisions V2-1 to V2-8 in `EXPERIMENT_V2.md` and the manifest is written:

```bash
python3 src/run_v2.py freeze v2-run-1 && python3 src/run_v2.py scored-batch
```

Reported after the run: correctness by group × condition; numerical error; tool-request, valid-execution and required-tool-compliance rates; invalid outputs, timeouts and other failures; actual calls, latency and thinking tokens; task-level paired differences with a cluster bootstrap over tasks; within-task variation; a tool-use failure taxonomy. If V2 also reaches a ceiling, or the optional tool still goes unrequested, that is the published outcome.

### What remains unresolved

Why the optional tool went unrequested in V1, and why it is requested every time in V2's clean development run: too much changed between the two systems to say. Whether the development gradient (no tool 2/2 → 1/2 → 0/2) and the tool effect hold on 18 held-out tasks with three repetitions: that is the scored run. Whether the no-tool failure mode (reaching for a code tool it does not have) is stable or prompt-sensitive. A second model family (Codex/GPT) is deferred because its CLI exposes no way to remove its shell tool.

---

## Reproduce without model calls

Python 3.11, standard library only.

```bash
python3 -m unittest tests.test_ls_slope tests.test_tasks tests.test_evaluate tests.test_agent tests.test_controls tests.test_analyze tests.test_v2_tasks tests.test_v2_agent tests.test_v2_run tests.test_v2_analyze tests.test_v2_pipeline
```

```bash
python3 src/analyze.py && python3 src/chart.py && python3 src/analyze_v2.py dev && python3 src/chart_v2.py dev
```

Regenerating the data (`python3 src/tasks.py`, `python3 src/tasks.py scored`, `python3 src/tasks_v2.py`, `python3 src/tasks_v2.py scored`) leaves every committed file unchanged. The same checks run in CI (`.github/workflows/checks.yml`). Scored inference needs a Claude subscription with the frozen CLI version; `src/run.py scored-batch` and `src/run_v2.py scored-batch` refuse to run unless every frozen file and the CLI version match their manifest, and never repeat an attempted episode. Raw CLI output (`results/raw/`) is not published because it contains session metadata; the reviewed per-call summaries are in the episode files.

## Repository map

| Path | What |
|---|---|
| `EXPERIMENT.md`, `data/freeze_manifest.json` | V1 frozen protocol and manifest |
| `EXPERIMENT_V2.md` | V2 protocol draft, development gate and approval decisions |
| `src/tasks.py`, `tools.py`, `evaluate.py`, `models.py`, `agent.py`, `run.py`, `analyze.py`, `chart.py` | V1 (frozen) |
| `src/*_v2.py`, `prompts/v2/`, `data/v2/`, `results/v2/` | V2; `results/v2/dev_stage1/` and `dev_stage2/` are superseded development snapshots with advisor audits |
| `results/episodes_scored.jsonl`, `results/summary.*`, `results/chart.svg` | V1 evidence and analysis outputs |
| `tests/` | 90 offline checks, including an end-to-end pipeline test (task → model choice → tool request → validated execution → returned result → final answer → deterministic score), including regression tests for every defect found in review |
| `RESEARCH_LOG.md`, `HANDOFF.md`, `RESEARCH_ROADMAP.md` | chronology, evidence and follow-ups |
| `PROPOSAL.md`, `LINEAGE.md` | a separate analytical-physics study proposed on branch `research/analytical-physics`; unapproved and unrun |

## Authorship

- **Leo (@retinapeg):** research question, design decisions and protocol approval.
- **Claude, via Claude Code, at Leo's direction:** the code, tests, analysis and documentation (V1 and V2).
- **Codex:** independent review. For V1 it reproduced both harness defects; for V2 it found three executable defects (interrupted-episode replay on resume, control violations hidden by a timeout, a numeric-overflow crash), all fixed with regression tests before any scored call.
- **A multi-agent Claude review** (five dimensions, two refuters per finding) found the server-side advisor in the development traces and ten further defects, all fixed with tests; the refuted findings are recorded in the session log.
