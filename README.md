# Agentic Physics Bench: V1 (release v1.0.0)

> Release naming: this is the pilot that the development log calls "V0". Leo named the finished release **V1** (git tag `v1.0.0`) on 2026-09-21. Earlier log entries keep their original wording.

A small, reproducible evaluation of one question: **on synthetic velocity–time measurements, how does a bounded line-fit tool workflow compare with a direct answer for estimating signed acceleration?** The system tested is Claude (`claude-opus-5`) through the Claude Code CLI 2.1.278, on 12 held-out cases. It is a pilot, so it supports no statistical significance claims and no model ranking.

## Result

| Condition | Correct (±0.01 m/s², units required) | Tool requested | Model calls | Median / max \|error\| (m/s²) |
|---|---|---|---|---|
| Direct answer | **12/12** | — | 12 | 1.1 × 10⁻⁴ / 4.5 × 10⁻⁴ |
| Bounded tool workflow (optional `fit_line`) | **12/12** | **0/12** | 12 | 2.1 × 10⁻⁴ / 1.5 × 10⁻³ |
| Deterministic least-squares solver (reference point) | 12/12 | — | — | 0 |

- **Paired comparison:** 12 ties, with 0 cases correct only under the workflow and 0 correct only under direct. All 24 planned episodes were attempted and valid: no invalid runs, missing outputs or retries. That used 24 model invocations against a cap of 36.
- **Answers:** every answer equals the reference slope rounded to between 1 and 6 decimals (24/24). The error denominators above are all 12 per condition, because every answer parsed with accepted units.
- **Hidden reasoning:** the CLI reported a median of about 480 output tokens per one-line answer, which includes hidden reasoning.

![Absolute error per scored case](results/chart.svg)

Table view: [`results/summary.md`](results/summary.md). Computed by [`src/analyze.py`](src/analyze.py) from [`results/episodes_scored.jsonl`](results/episodes_scored.jsonl).

**What this shows:**
- On this task, the system reproduced the least-squares slope to within rounding, in both conditions.
- Given an optional tool, it never used it, so both conditions sat at the ceiling.

**What it does not show:**
- Any effect of tool access. The tool was never exercised in a scored episode, so the pilot cannot measure a tool benefit.
- Anything about other models, other tasks or harder problems.
- That a language model is needed. An ordinary least-squares function solves the task exactly.

## System architecture

![Architecture at v1.0.0: seeded synthetic cases feed a runner that calls Claude through the Claude Code CLI, directly or through a bounded fit_line loop; a deterministic grader compares answers with hidden keys, and offline scripts summarise the saved traces](docs/images/architecture.svg)

*Purple: model call · blue: deterministic code · green: human · amber: evaluation · grey: storage · dashed: external, optional, mocked or planned*

As of v1.0.0, `src/tasks.py` writes seeded synthetic cases, and their reference slopes go to separate key files that neither the model nor the tool receives. `src/run.py` checks the freeze manifest before a scored batch and sends a prompt built from the displayed numbers to Claude through the Claude Code CLI: once in the direct condition, or through the bounded loop in `src/agent.py`, which validates any `fit_line` request and runs it at most once. Each call is checked against the controls, `src/evaluate.py` grades the parsed answer against the hidden key, and every episode is appended to `results/episodes_*.jsonl`. `src/analyze.py` and `src/chart.py` build the summary and chart from those saved traces without calling a model.

## How AI is used

- **Model and role:** Claude (`claude-opus-5`, requested effort `high`) through the Claude Code CLI 2.1.278, on a Claude subscription rather than an API key. It is the system under test; the harness makes no other model calls.
- **Input:** a prompt from `prompts/*.txt` filled with the case's displayed times and velocities. In the workflow's second call it also gets its previous reply and the `fit_line` result. It never sees the reference key.
- **Output:** exactly one JSON object, either a final answer or (workflow only) a `fit_line` request, parsed without repair or retry.
- **Tools and permissions:** the CLI's native tools, MCP servers and session persistence are off, and each call runs in safe mode in an empty temporary directory. The model can only request `fit_line`; the harness validates the request and executes it.
- **Deterministic or human-controlled:** case generation, the loop, control checks, grading, analysis and the chart are standard-library Python. Leo approved the protocol freeze, and after an invalid scored run no further inference happens until he decides.
- **Evaluation and limits:** answers must be within ±0.01 m/s² of the least-squares reference, with units. See [Method](#method) and [Limitations](#limitations).

## Failure review

- **Model errors in scored episodes: none.** The closest case is s-07 in the workflow condition: it answered −3.6 against a reference of −3.601455, an error of 1.5 × 10⁻³. That is consistent with rounding to 2 decimals.
- **Harness errors, found in review before scoring and reproduced independently by Codex:**
  1. A tool request with `"name": []` crashed validation with a TypeError.
  2. The runner could record a failed control alongside a correct grade.

  Both were fixed before the freeze. Regression tests fail on the old code and pass on the fix (`tests/test_agent.py`, `tests/test_controls.py`).
- **Configuration hazard:** the CLI does not reject an unknown `--effort` value. It prints a stderr warning, uses the default and still calls the model. So the runner treats any stderr output as a control violation. No scored call produced stderr output.

## Method

- **Task and reference:**
  - 10 points at t = 0, 0.5, …, 4.5 s; noise σ = 0.5 m/s; velocities shown to 2 decimals.
  - `a_true` is continuous in ±(0, 5] m/s², with the 6/6 sign balance on the generating value.
  - The reference is the least-squares slope of exactly the displayed numbers, checked against `statistics.linear_regression` and exact fraction arithmetic.
- **Conditions:**
  - *Direct:* one model call, answering in strict JSON.
  - *Workflow:* the model may request `fit_line` by case ID. The harness validates the request and supplies that case's displayed data, never the key. A fresh second call gets the task, the previous reply and the tool result. At most 2 calls and 1 tool execution, no retries.
- **Controls, enforced per call:**
  - no native tools or MCP servers; safe mode; an empty temporary working directory;
  - the expected model ID, with the CLI version present in the initialization metadata;
  - no tool use, no overage, no stderr output.

  Any violation invalidates the episode and stops the batch. The exact CLI version, the CLI arguments and the hashes of the frozen files are checked once, before the batch starts (`verify_freeze` in `src/run.py`).
- **Freeze:** the protocol, prompts, data, code hashes and run order were committed and tagged `v0-protocol-freeze` before any scored call. See [`EXPERIMENT.md`](EXPERIMENT.md) and [`data/freeze_manifest.json`](data/freeze_manifest.json).

## Scope of V1

V1 contains one task family (4 development and 12 scored cases), the Claude CLI adapter, the direct vs optional-`fit_line` conditions, the bounded loop with request validation and enforced controls, deterministic grading, saved traces, offline checks, failure reporting, and analysis from saved results. It has no RAG, memory, symbolic tools, other task families or other model integrations. GPT/Codex was deferred because its controls were not verified.

## Limitations

- 12 cases and one system; this is a pilot.
- The Claude Code CLI adds its own instructions, which were not verified. Results describe that system, not the bare model.
- `fit_line` returns exactly the reference, so tool use plus faithful copying would guarantee a correct answer. The optional wording let the model skip it.
- The effort setting (`high`) can't be confirmed from traces, only the absence of the fallback warning.
- The CLI's reported input-token totals don't track prompt length, so they are not used.
- The prompts were fixed after two development episodes on dev-01; the other development cases were never run. The development and scored splits use different seeds.

## Reproduce

Check out the release with `git checkout v1.0.0`. Needs Python 3.11, standard library only. Scored inference also needs a Claude subscription with Claude Code 2.1.278.

Release audit (2026-09-21), on a fresh clone from GitHub:
- all 36 offline checks pass;
- regenerating the data leaves every file unchanged;
- `src/analyze.py` and `src/chart.py` reproduce `results/summary.json`, `summary.md` and `chart.svg` byte for byte;
- `verify_freeze` passes.

```bash
python3 -m unittest tests.test_ls_slope tests.test_tasks tests.test_evaluate tests.test_agent tests.test_controls tests.test_analyze
```

```bash
python3 src/analyze.py && python3 src/chart.py
```

`python3 src/run.py scored-batch` refuses to run unless every file and the CLI version match the freeze manifest. It never repeats an attempted episode. Raw CLI output (`results/raw/`) is not published because it contains session metadata; the reviewed per-call summaries are in the episode files.

## Authorship

- **Leo (@retinapeg):** research question, design decisions and protocol approval.
- **Claude, via Claude Code, at Leo's direction:** the code, tests and documentation.
- **Codex:** independent review (it reproduced both harness defects), the GPT smoke test and the research addendum.

The chronology and evidence are in [`HANDOFF.md`](HANDOFF.md) and [`RESEARCH_LOG.md`](RESEARCH_LOG.md). Follow-up experiments are in [`RESEARCH_ROADMAP.md`](RESEARCH_ROADMAP.md).
