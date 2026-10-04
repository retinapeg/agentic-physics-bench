# V3 morning report — 2026-10-04

## Status

**SYNTHETIC offline rehearsal only. No real model calls, development pilot, scored run, or held-out exposure occurred.** V3 is still a draft. The synthetic records are diagnostic fixtures and must not be interpreted as model behaviour.

## What was built and checked

The V3 draft currently has `EXPERIMENT_V3.md`; `src/tasks_v3.py`, `src/grade_v3.py`, `src/sandbox_v3.py`, and `src/run_v3.py`; `tools_v3/qm_tool.py`; three prompt files; separate development and held-out public tasks and private keys; and four V3 test files. This step added `src/dryrun_v3.py` and `results/v3/dryrun/{episodes.jsonl,summary.json}`. The rehearsal drives prompt rendering, scripted provider event parsing, per-turn control checks, first-answer grading, honesty classification, and output writing. The existing sandbox tests exercise local staging and the host-side tool log. The rehearsal itself injects **synthetic** log events; it does not prove that a live CLI call is captured by the boundary.

`python3 -m unittest discover -s tests -p 'test_v3_*.py' -v`: **24 passed, 0 failed**. NumPy 1.26.0, SciPy 1.11.3, and SymPy 1.14.0 imported successfully. No V1/V2 file was changed.

## Dry-run results

`python3 src/dryrun_v3.py` used all eight public development tasks, four conditions, one synthetic repetition, and two scripted provider streams. The Claude stream completed 32/32 valid two-turn episodes. Codex stopped at its first synthetic episode because `codex_controls_unverified` is an intentional fail-closed gate. Thus 33/64 possible cells were attempted, 32 valid and one invalid. All fake first answers were the constant zero; 0/32 graded correct. This is a pipeline fixture, not an accuracy estimate.

| Scripted Claude condition | Episodes | Synthetic executions | Correct | False denials |
|---|---:|---:|---:|---:|
| A, absent | 8 | 0 | 0 | 0 |
| B, optional | 8 | 8 | 0 | 0 |
| C, forbidden | 8 | 1 | 0 | 1 |
| D, unmentioned | 8 | 4 | 0 | 0 |

The one C execution is a synthetic rule violation. Raw synthetic episode classifications are in `dryrun/episodes.jsonl`; aggregate counts are in `dryrun/summary.json`. Neither file contains private reference answers.

## Exact intended development-pilot invocation

The human pilot specification is **Codex `gpt-6-sol` primary, Claude `claude-sonnet-5` secondary; six development tasks × four conditions × two models × one repetition = 48 episodes, at most 120 model calls**, with the STOP file checked before each episode and each call. A proposed invocation, once a guarded pilot CLI exists and its controls pass, is:

```sh
python3 src/run_v3.py dev-pilot --primary codex:gpt-6-sol --secondary claude:claude-sonnet-5 --tasks d-01,d-02,d-03,d-05,d-06,d-07 --conditions A,B,C,D --reps 1 --max-calls 120 --stop-file results/v3/STOP --output results/v3/dev_pilot
```

**Do not run that command yet:** `src/run_v3.py` has no `dev-pilot` CLI, plan, call-cap, or STOP-file loop. Its Codex adapter rejects the second turn because tool disablement is unverified, and its Codex audit rejects all calls because model identity and other controls are not observable in the current stream. The command above states the exact intended parameters, not an available executable pilot. The six task IDs are a proposed balanced subset (three numeric, three symbolic); confirm selection and order seed before any development calls. A live pilot also requires evidence that both requested model identifiers are available and auditable.

## Decisions required before freezing

1. **Repair public task rendering.** The prompt currently inserts `task["question"]` without `task["parameters"]`, although several questions refer to “displayed” values. Determine and freeze an unambiguous rendering that includes every parameter, then recheck all development and held-out task statements before exposure.
2. **Choose and enforce one tool boundary.** The protocol says one instrumented computational tool. The Claude draft exposes `Read` and general `Bash(python3:*)`; the staged `qm_tool.py` logs only its own invocation. General Python execution could escape that log. A, C, and the no-tool honesty turn need audited physical permissions, not prompt text alone. Codex's current sandbox does not demonstrate equivalent controls.
3. **Make per-call audit evidence complete.** Verify actual model identity, CLI version, provider-side tools/auxiliary models, turn-two tool denial, external invocation and blocked-attempt logging, sandbox identity, and log/transcript reconciliation for both adapters. Stop a provider if any control remains unverified.
4. **Implement the pilot plan and limits.** Freeze the six-task selection, seeded order, one repetition, append-only attempt records, 120-call cap, STOP-file behavior, interruption handling, and resume without replay. Keep development separate from held-out and scored records.
5. **Set grading and task criteria.** Validate units, six-decimal versus significant-figure tolerances, symbolic equivalence and ambiguity handling, and numerical stability with offline independent checks. Decide whether the proposed task mix is sufficiently tool-beneficial and whether a development ceiling requires a new draft and held-out set.
6. **Resolve protocol status and freeze contents.** `EXPERIMENT_V3.md` currently says “DRAFT, frozen by Leo” while also saying no V3 tasks or harness exist; update that status when the protocol is reviewed. A later approved manifest must hash the complete protocol, tasks/keys, prompts, runner, detector, grader, analysis, execution plan, dependency versions, and sandbox configuration before scored inference.

## Uncertainty

The fake streams exercise branching and record shapes, not provider behaviour. No real CLI capabilities, model availability, permission isolation, STOP-file behavior, 120-call enforcement, or live boundary detection was verified. The 0/32 synthetic correctness rate and condition use counts carry no empirical meaning.
