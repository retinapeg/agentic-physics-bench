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
| Result | **12/12 and 12/12 correct; the optional tool was requested 0/12 times** | development: no tool 6/6, optional 6/6 (tool requested 6/6), required 6/6; scored run pending approval |
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

### System architecture (V1)

![Architecture at v1.0.0: seeded synthetic cases feed a runner that calls Claude through the Claude Code CLI, directly or through a bounded fit_line loop; a deterministic grader compares answers with hidden keys, and offline scripts summarise the saved traces](docs/images/architecture.svg)

*Purple: model call · blue: deterministic code · green: human · amber: evaluation · grey: storage · dashed: external, optional, mocked or planned*

As of v1.0.0, `src/tasks.py` writes seeded synthetic cases, and their reference slopes go to separate key files that neither the model nor the tool receives. `src/run.py` checks the freeze manifest before a scored batch and sends a prompt built from the displayed numbers to Claude through the Claude Code CLI: once in the direct condition, or through the bounded loop in `src/agent.py`, which validates any `fit_line` request and runs it at most once. Each call is checked against the controls, `src/evaluate.py` grades the parsed answer against the hidden key, and every episode is appended to `results/episodes_*.jsonl`. `src/analyze.py` and `src/chart.py` build the summary and chart from those saved traces without calling a model.

### How AI is used (V1)

- **Model and role:** Claude (`claude-opus-5`, requested effort `high`) through the Claude Code CLI 2.1.278, on a Claude subscription rather than an API key. It is the system under test; the harness makes no other model calls.
- **Input:** a prompt from `prompts/*.txt` filled with the case's displayed times and velocities. In the workflow's second call it also gets its previous reply and the `fit_line` result. It never sees the reference key.
- **Output:** exactly one JSON object, either a final answer or (workflow only) a `fit_line` request, parsed without repair or retry.
- **Tools and permissions:** the CLI's native tools, MCP servers and session persistence are off, and each call runs in safe mode in an empty temporary directory. The model can only request `fit_line`; the harness validates the request and executes it.
- **Deterministic or human-controlled:** case generation, the loop, control checks, grading, analysis and the chart are standard-library Python. Leo approved the protocol freeze, and after an invalid scored run no further inference happens until he decides.
- **Evaluation and limits:** answers must be within ±0.01 m/s² of the least-squares reference, with units. See the method and limitations below.

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

### Development check (not scored)

The development set is six tasks, two per group. The final calibration combines stage 3 (tool conditions; CLI 2.1.280, `claude-opus-5`, effort high, the CLI's server-side advisor disabled, controls enforced per call) with stage 4, which reran only the no-tool condition after Leo fixed its wording (decision V2-4b: "No tools or code execution are available. Compute the answer from the table."). Earlier stages are archived: stages 1–2 are void because a server-side advisor had consulted `claude-fable-5-1` inside 31 of their 48 calls; stage 3's no-tool records are kept as a finding in their own right (`results/v2/dev_stage1/`, `dev_stage2/`, `dev_stage3/`).

![Development results: proportion correct by group and condition](results/v2/chart_dev.svg)

| Group (points) | No tool (stage 4, explicit wording) | No tool (stage 3, earlier wording) | Optional tool (requested / executed) | Required tool (compliant) |
|---|---|---|---|---|
| easy (10) | 2/2 | 2/2 | 2/2 (2 / 2) | 2/2 (2/2) |
| moderate (24) | 2/2 | 1/2 | 2/2 (2 / 2) | 2/2 (2/2) |
| hard (40) | 2/2 | 0/2 | 2/2 (2 / 2) | 2/2 (2/2) |

Table view with errors, latency, thinking tokens and the failure taxonomy: [`results/v2/summary_dev.md`](results/v2/summary_dev.md).

- **Told explicitly that it has no tools, the model does the arithmetic itself.** Stage 4: 6/6 correct without the tool, every first reply already a correct number; median thinking tokens per call 642 / 2130 / 6368 and median 10 / 25 / 62 s per call (easy / moderate / hard). On the development set the no-tool condition is at the ceiling.
- **Under the earlier wording it reached for code instead.** Stage 3: every moderate and hard first reply was an attempt to run code the system does not have (a fenced bash block or tool-call syntax), and the second-turn numbers were outside tolerance on 3 of 4. That is recorded as a harness/system finding, not carried into the scored baseline.
- **With the tool available, it was used and relayed exactly.** Optional tool requested at turn 1 in 6/6 episodes with no recorded thinking tokens; required-tool compliance 6/6; every returned slope relayed with zero error.
- Two tasks per group support no claim beyond "the mechanism works and the calibration is at ceiling". Grader, tolerance and tasks were not changed on these outcomes; the scored run measures whether the ceiling holds on 18 held-out tasks with three repetitions.

**What the development check taught us.** The first two development stages looked like a ceiling, in line with V1. The independent review then found, in one raw trace, a server-side `advisor` tool that had consulted `claude-fable-5-1` inside a call made with `--tools ""`; an audit found it in 31 of 48 calls. V1's controls check the CLI's tool list and each assistant message's model, neither of which shows a server-side tool or a second model in the usage report. V1's own 24 scored traces show only `claude-opus-5`, so V1 stands. V2 now disables the advisor by environment variable, records that in every episode and the manifest, and invalidates any call that reports a server-side tool, a second model or a non-message iteration. The second lesson came from the prompt: without an explicit statement that no code execution exists, the no-tool condition measured code-seeking, not arithmetic. The V1 vs V2 tool-request rates (0/12 vs 6/6 optional requests, 2/2 on easy tasks) remain **not attributable**: the CLI version, the two-turn design, prompt sentences and the advisor state all differ.

### Scored run: pending approval

18 tasks × 3 conditions × 3 repetitions = 162 episodes, exactly 2 calls each = 324 calls, one system. The protocol is frozen (`data/v2/freeze_manifest.json`, run `v2-run-1`, 21 hashed files, CLI 2.1.280, advisor disabled); the batch runs only on Leo's go:

```bash
python3 src/run_v2.py scored-batch
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
| branch `research/analytical-physics` | a separate analytical-physics study (its `PROPOSAL.md`, `LINEAGE.md`); unapproved, unrun, not part of this branch |

## Authorship

- **Leo (@retinapeg):** research question, design decisions and protocol approval.
- **Claude, via Claude Code, at Leo's direction:** the code, tests, analysis and documentation (V1 and V2).
- **Codex:** independent review. For V1 it reproduced both harness defects; for V2 it found three executable defects (interrupted-episode replay on resume, control violations hidden by a timeout, a numeric-overflow crash), all fixed with regression tests before any scored call.
- **A multi-agent Claude review** (five dimensions, two refuters per finding) found the server-side advisor in the development traces and ten further defects, all fixed with tests; the refuted findings are recorded in the session log.
