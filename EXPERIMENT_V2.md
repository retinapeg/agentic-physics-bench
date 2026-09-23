# EXPERIMENT_V2.md — V2 protocol: task difficulty × tool policy

Status: **FROZEN as `v2-run-1` (14:06 BST) and RUN (15:11–16:35 BST, 2026-09-23).** Run record: section 12. Written by Claude at Leo's direction. Nothing in this document
is frozen until `data/v2/freeze_manifest.json` exists; the scored batch refuses to run without it. The
development gate (section 9) runs before the freeze; the scored batch runs only after Leo's approval
(section 11). V1 (`EXPERIMENT.md`, tag `v1.0.0`) is unchanged, and every V1 file in its freeze manifest is
untouched: V2 is new modules that import V1's reference function, tool, parser, grader, CLI adapter and
control checks.

## 1. Question

As numerical physics tasks become more demanding, how do optional versus required tool workflows affect
correctness, tool uptake and failure modes?

V1 motivates this: on 12 easy held-out tasks the tool-enabled system returned correct answers without ever
requesting the optional tool, and both conditions reached the scoring ceiling. V2 separates four things V1
could not: whether the tool mechanism works live (the required condition), whether the model elects to
request it (the optional condition), whether it uses a returned result correctly (relay fidelity), and how
all three move with difficulty (three groups). V2 is **not** a replication of V1: every condition now has two
model turns, and the tasks, seeds and plan are new (section 8).

## 2. Tasks: one family, three difficulty groups

Same family as V1: a table of (t [s], v [m/s]) pairs; report the signed acceleration as the least-squares
slope of v against t, in m/s². Reference = the least-squares slope of exactly the displayed strings (never
the generating value), checked in tests against `statistics.linear_regression` and exact fraction arithmetic.

| Group | Points | Time grid | Shown t / v | Noise σ | Generator |
|---|---|---|---|---|---|
| easy | 10 | t = 0.5·i s, i = 0…9 (uniform) | 1 dp / 2 dp | 0.5 m/s | V1's `tasks.make_case`, exactly, with a new seed |
| moderate | 24 | t = 0.5·i + U(0, 0.4) s (irregular) | 2 dp / 2 dp | 1.0 m/s | `tasks_v2.make_case_v2` |
| hard | 40 | t = 0.5·i + U(0, 0.4) s (irregular) | 2 dp / 2 dp | 2.0 m/s | `tasks_v2.make_case_v2` |

Common to all groups (V1's values): |a_true| continuous in (0, 5] m/s², sign-balanced within each group
(alternating −, +), no magnitude floor or redraw; v0 uniform on [−10, 10] m/s; one `random.Random(seed)` per
(split, group); draw order |a_true|, v0, then every time offset, then one noise value per point. Displayed
times are strictly increasing by construction (the offset is at most 0.4 s, below Δt = 0.5 s, so consecutive
times differ by at least 0.1 s before rounding).

Difficulty levers are the volume of arithmetic (N), the loss of the symmetric-grid shortcut (irregular
times) and the noise. The displayed precision and the acceleration range are V1's, so the scoring rule can
stay fixed (section 5).

- Development: 6 tasks (`d1-01`…`d3-02`; two per group), seeds 1101/1102/1103.
- Scored: 18 tasks (`g1-01`…`g3-06`; six per group), seeds 2201/2202/2203. Not shown to any model before the freeze.
- Files: `data/v2/{dev,scored}_tasks.jsonl` (what a model sees), `..._keys.jsonl` (never shown), `..._plan.json`.

## 3. Conditions

Three conditions, identical task text, identical output schema, **two fresh model calls in every condition**
and at most one tool execution. The final answer is always turn 2's reply, so every condition gets the same
opportunity to revise; V1's one-call baseline is not compared with a two-call workflow.

| Condition | Turn 1 prompt | Tool | Turn 2 |
|---|---|---|---|
| `no_tool` | task; "No tools or code execution are available. Compute the answer from the table."; reply with the final JSON (V2-4b, Leo) | none; a tool request is recorded, not executed | "You may check your calculation and revise" |
| `optional_tool` | task; "You may use one tool" (V1 wording) | `fit_line` by case ID, validated as in V1 | tool result if a valid request was made, otherwise a message saying no tool result exists |
| `required_tool` | task; "you must use one tool"; only the request format is shown | same | same; a final answer at turn 1 is recorded as **noncompliance** and the episode still gets turn 2 |

Turn 2 is one template (`prompts/v2/turn2.txt`): the original task, the model's previous public reply
verbatim, a "tool section" stating exactly what happened (result / no request / invalid request with its
code / required but not requested / tool failed / unparsed reply), then the final-answer instruction. The
required condition is a diagnostic intervention: it tests the mechanism and relay fidelity, not voluntary
tool use. Prompts: `prompts/v2/*.txt`, hashed in the manifest.

Loop rules (`src/agent_v2.py`): no retries; a transport failure at turn 1 (no reply) ends the episode as
`missing_output`; model text that fails to parse still gets the fixed second turn, with the text shown; a
tool request at turn 2 is `tool_request_at_final_turn` (nothing executes); an invalid request is recorded
with its validation code and nothing executes. The tool receives only the displayed case, never the key.

## 4. Output protocol

Unchanged from V1: `{"type": "final", "acceleration": <number>, "units": "m/s^2"}`, accepted units
`m/s^2`, `m/s²`, `m s^-2`; tool request `{"type": "tool", "name": "fit_line", "arguments": {"case_id": "<id>"}}`;
exactly one JSON object, no repair, no retry (`src/evaluate.py`, `src/tools.py`).

## 5. Scoring

Correct iff the turn-2 reply parses, has accepted units and |answer − a_ref| ≤ **0.01 m/s² absolute**, in every
group (V1's D2). Same rule, harder data. Justification by V1's method, simulating each group with the shipped generator
(`tasks_v2.make_case_v2`, 4,000 draws per group, seed 7; `RESEARCH_LOG.md`, 2026-09-23): under ±0.01 the endpoint
slope passes 7.3 % / 6.9 % / 5.7 % (easy / moderate / hard), the split-halves slope 12.4 % / 22.6 % / 26.0 %, a
10-point subsample 100 % / 13.3 % / 8.4 %, and ignoring the time jitter (rounding times to the 0.5 s grid) — /
43.2 % / 66.2 %; rounding the exact slope to 2 decimals passes 100 %, and rounding the velocities to 1 decimal
88.8 % / 100 % / 100 %. The tolerance therefore rejects these named shortcuts in most draws in every group (on the
easy uniform grid a 10-point subsample is the full fit, so it passes by construction). It does not exclude every
approximate method, and an answer inside ±0.01 does not by itself show that a full least-squares fit was carried out
without demanding more precision than a 2-decimal answer. Continuous |error| is reported alongside.

Secondary: the turn-1 answer, when it is a final answer, is graded with the same rule (the V1-style
single-call result); relay fidelity |final − tool slope| for executed episodes.

## 6. Systems and controls

Primary system: Claude Code CLI **2.1.280** (the installed version; V1 used 2.1.278), `claude-opus-5`,
effort `high`, V1's argv (`--tools "" --safe-mode --strict-mcp-config --no-session-persistence`), empty
temporary working directory, prompt on stdin, fresh process per call. Per-call timeout 600 s (V1: 180 s).
Enforced per call (`src/run.py` `control_violations`, reused; plus `src/run_v2.py` `v2_control_violations`):
missing or unexpected init metadata, native tool use, MCP servers, overage, an unexpected model, stderr
output, a CLI version other than the frozen one, **any server-side tool block, any model other than
`claude-opus-5` in the reported usage, or any non-message iteration** invalidates the episode
(`invalid_run`, not graded, in the denominator) and stops the batch.

**Server-side advisor (found 2026-09-23, development stage 1).** CLI 2.1.280 can run a server-side
"advisor" tool that consults a second model (`claude-fable-5-1`) inside one call, even with `--tools ""`
and `--safe-mode`. It appears in the trace as `server_tool_use` / `advisor_tool_result` blocks, an
`advisor_message` iteration and a second `modelUsage` entry. V1's controls checked neither, so 24 of 36
stage-1 calls and 25 of 36 stage-2 calls passed as valid although the system under test was not
`claude-opus-5` alone (audits: `results/v2/dev_stage1/advisor_audit.json`, `dev_stage2/advisor_audit.json`).
V1's 24 scored traces show only `claude-opus-5`, so V1 is unaffected. V2 sets
`CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` for every call (recorded in every episode and in the manifest;
`verify_freeze` checks it) and enforces the three checks above. A probe with the variable set ran only
`claude-opus-5`. A timeout is an outcome (`missing_output`), not a violation; three
consecutive timeouts stop the batch. Recorded per call: elapsed time, reported output and thinking tokens,
five-hour and seven-day usage-window utilisation; never session IDs or paths.

Second system (Codex CLI / GPT): **deferred**. `codex exec` exposes no way to remove its shell tool (the
sandbox limits execution, not the tool), the local config enables live web search, and its JSONL does not
name the served model. Detection-only controls would be weaker than V1's and need a separate approval.

## 7. Matrix, order and budget

18 tasks × 3 conditions × 3 repetitions = **162 scored episodes**, exactly 2 calls each = **324 calls**, the
hard cap. Development: 6 tasks × 3 conditions × 1 repetition = 18 episodes, 36 calls. Execution order
(`data/v2/scored_plan.json`, seed 3303): repetition blocks run one after another; within a block the tasks
are shuffled and each task's three conditions run back to back in a shuffled order, so an interruption
leaves whole blocks or whole tasks complete. Resume never repeats an attempted (task, condition, repetition).
A substantive protocol change requires a new `run_id` and a new results file, not a mixed one. In
development, a gate decision that changes tasks or prompts archives the current development files under
`results/v2/dev_<stage>/` and starts a fresh episode file (`python3 src/run_v2.py dev-restage <stage>`,
optionally carrying over records of unchanged tasks); the runner never repeats a key within one file. The task
seeds, the plan seed and the model's own sampling are separate; the CLI exposes no sampling control.

## 8. Differences from V1 (declared)

Two turns in every condition (V1: direct = 1 call, workflow ≤ 2); a no-tool control and a required-tool
condition (new); three repetitions (V1: one); three difficulty groups (V1: one); CLI 2.1.280 (V1: 2.1.278);
600 s timeout; new seeds and a randomised plan. The easy group uses V1's generator and scoring rule, so it is
the closest point of comparison, but it is not a replication.

## 9. Development gate (declared before any development call)

Run the 18 development episodes once (`python3 src/run_v2.py dev`). Then check, and record in
`RESEARCH_LOG.md`:

- **G-a, harness live:** every episode uses exactly 2 calls, no control violations; in `required_tool` at
  least one valid request executes and its result appears in the saved turn-2 prompt.
- **G-b, difficulty:** `no_tool` correctness and |error| per group, reported as observed.
- **G-c, format:** malformed outputs attributable to prompt wording (e.g. fenced JSON) allow one round of
  prompt-wording revision, re-checked on the affected development condition; the grader, tolerance and
  task data are not changed on development evidence.
- **Escalation, at most once:** if `no_tool` is correct on every moderate and hard development task, raise
  the hard group to 60 points (same other parameters), regenerate the hard development tasks only, and run
  those 6 episodes again (12 calls). Then freeze regardless of the outcome. If V2 still reaches a ceiling or
  still produces no optional requests, that is the published result. *Applied once on stage 1 and reverted
  with it; not applicable to stage 4 (Leo, 2026-09-23: the stage-4 rerun verifies that difficulty remains
  non-ceiling; grader, tolerance and tasks are not altered on its outcome).*

Every development episode stays in `results/v2/episodes_dev.jsonl`, including any before a wording change.

**Gate record (2026-09-23; details in `RESEARCH_LOG.md`).**
- *Stages 1 and 2 are void for the gate.* Stage 1 (18 episodes, hard = 40, original wording) and stage 2
  (the six hard episodes at 60 points with the revised wording, easy/moderate carried over) were run before
  the server-side advisor was discovered (section 6); 16 of 18 episodes in each stage used it. Both stages
  are archived verbatim with audits (`results/v2/dev_stage1/`, `dev_stage2/`). The escalation to 60
  points taken on stage 1 was reverted: the hard group is 40 points again, and the escalation clause is
  re-applied once, on stage 3 only. The wording revision from stage 1 (one fenced-JSON reply → "(no code
  fences, no other text)" in every prompt) is kept, since G-c allows exactly one.
- *Stage 3* is the full development plan (18 episodes, 36 calls) with the advisor disabled and the amended
  controls enforced per call, on a fresh `results/v2/episodes_dev.jsonl`. **Outcome (12:48–12:56 BST):** 36/36
  calls report `claude-opus-5` only, no server-side tool, no violations; 18/18 valid. `no_tool` correct 2/2 easy,
  1/2 moderate, 0/2 hard (every moderate and hard turn-1 reply was an attempt to run code, then a number outside
  tolerance on 3 of 4 at turn 2); `optional_tool` requested and executed 6/6, correct 6/6 with exact relay;
  `required_tool` compliant 6/6, correct 6/6. G-a passed; G-b shows the gradient; G-c: the failures are code
  attempts, not fence-wrapped JSON, and the one wording revision is spent. The escalation clause did **not**
  fire: the hard group stays at 40 points. **Freeze-ready**, pending section 11.
- *Stage 4* (14:05–14:13 BST; Leo's V2-4b): the six `no_tool` episodes rerun with the explicit baseline sentence;
  the twelve tool-condition records carried over from stage 3 unchanged. **Outcome:** `no_tool` correct 6/6 (2/2,
  2/2, 2/2), every turn-1 reply a well-formed number, max |error| 2.8e-04 m/s²; median thinking tokens per
  call 642 / 2130 / 6368 and median 10 / 25 / 62 s per call (easy / moderate / hard; hard max 94 s).
  Under the explicit constraint the system returned every no-tool answer inside tolerance, so **the no-tool
  condition is at the ceiling on these six development tasks**. How the answers were produced is not observed: the
  CLI redacts the model's reasoning, so the record holds only the returned values and the thinking-token counts;
  "computed the regression itself" is an inference from those, not an observation. Per Leo's instruction, grader, tolerance
  and tasks are not altered on this outcome; the scored run measures whether that holds on 18 held-out tasks with
  three repetitions, and a ceiling there is a publishable result.
- *Development calls consumed on 2026-09-23:* 1 smoke check + 36 (stage 1) + 12 (stage 2) + 1 advisor probe +
  36 (stage 3) + 12 (stage 4) = **98 calls**, all logged (stages in `results/v2/`, the smoke and probe traces outside
  the repo).

## 10. Analysis (fixed before scoring)

`src/analyze_v2.py` from the saved episodes only: correctness by group × condition (correct / planned);
outcome counts including `not_attempted` and `invalid_run`; |error| median and max among parseable
answers; tool requested / valid / executed; required-tool compliance; relay fidelity; turn-1 correctness
and revisions; timeouts, calls, elapsed time, output and thinking tokens; per-task proportions over
repetitions; task-level paired differences (optional − no tool, required − no tool, required − optional)
with a seeded cluster bootstrap over tasks (2,000 resamples; 95 % percentile interval); within-task
variation; a tool-use failure taxonomy (invalid request / execution failure / executed then unparseable /
executed then wrong / required noncompliant). Repeated calls on one task are clustered, not independent.
No causal tool benefit is inferred from comparing optional episodes that requested the tool with those that
did not. Boundary results (all-success, all-zero) are reported as counts with their limits. Figure:
`src/chart_v2.py`.

## 11. Decisions for one approval (Leo)

**Evidence for the request (from development stage 3, 2026-09-23).** System: Claude Code 2.1.280, `claude-opus-5`,
effort `high`, V1's argv, `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1`. Confirmed by metadata on 36/36 stage-3 calls: init
`model` = `claude-opus-5`, `claude_code_version` = 2.1.280, `modelUsage` = `claude-opus-5` only, no server-side
tool, `apiKeySource` none, overage rejected. Requested but not confirmable from traces: effort `high` (as in V1;
only the absence of the fallback warning is checked). Scored run: 162 episodes, exactly 324 calls (the cap), with
no further development calls; 98 development calls were used today (section 9). The final development set (stage 3's
tool-condition records plus stage 4's no-tool records, 36 calls) used 128,418 reported input tokens (mostly cache
reads) and 37,946 output tokens in 574 s; scaled ×9, the scored run is about 1.2 M reported input tokens,
342 k output tokens and 1.4 h, most of it in the hard no-tool episodes (62–94 s per call). Usage windows
after stage 4: five-hour 51 %, seven-day 33 %. Stop limits: cap 324 calls; stop on any invalid run (including a
server-side tool or a second model), a rate-limit status other than allowed, or three consecutive timeouts;
600 s per call; no retries. Fallback: repetition block 1 only (`--max-episodes 54`, 108 calls).

| # | Decision | Recommendation |
|---|---|---|
| V2-1 | Groups and parameters | Section 2 as tabled (hard = 40 unless the stage-3 escalation clause fires) |
| V2-2 | Tolerance | ±0.01 m/s² absolute in every group (V1's), with the shortcut simulation as justification |
| V2-3 | Conditions and turn structure | Section 3; two calls in every condition; required-tool noncompliance continues to turn 2 and is reported separately |
| V2-4 | Required-tool wording | Show only the request format at turn 1 (section 3) |
| V2-4b | No-tool prompt | **Decided by Leo (2026-09-23):** the no-tool turn-1 prompt states "No tools or code execution are available. Compute the answer from the table." so the baseline is unambiguous about tool availability. The stage-3 observation that the earlier prompt made every moderate and hard no-tool turn attempt unavailable code remains documented as a harness/system finding (`results/v2/dev_stage3/`, `RESEARCH_LOG.md`). Only the affected development condition was rerun (stage 4); grader, tolerance and tasks unchanged |
| V2-5 | Matrix | 18 × 3 × 3 = 162 episodes, 324 calls, single system; fallback 18 × 3 × 1 = 54 episodes, 108 calls, run as block 1 |
| V2-6 | Timeout, environment and stop rules | 600 s per call; `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1`; stop on invalid run (including any server-side tool or second model), rate limit or 3 consecutive timeouts; cap 324 |
| V2-7 | Second system | Deferred (section 6); optional later approval |
| V2-8 | Publication | Merge the branch to `main` after the run; V1 files and results untouched |

## 12. Run record (2026-09-23)

Leo's go at ~15:05 BST after the corrections of section 11's count and two qualified claims. Availability probe before starting: status allowed, five-hour window 64 %, seven-day 36 % (one minimal call). The batch ran in two resumable chunks with the frozen runner (`--max-episodes 39`, then the remainder) to stay clear of a quota stop mid-episode; resume repeated nothing. Attempted 162/162, valid 162, invalid 0, interrupted 0, calls 324 of the cap 324, timeouts 0, stop reason `completed`; every call `claude-opus-5` only, no server-side tool. Usage windows after the last call: five-hour 11 %, seven-day 42 %. Results: `results/v2/episodes_scored.jsonl`, `summary_scored.{json,md}`, `chart_scored.svg`; interpretation in the README and `RESEARCH_LOG.md`. No file in the manifest changed (`verify_freeze` passes after the run).
