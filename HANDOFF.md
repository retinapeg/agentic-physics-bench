# Handoff: branch `v2/tool-policy` (last updated 2026-09-23; see the V2 section below, then the inherited sections)

**Canonical paths (Leo's one-repo decision, 2026-09-22):** repository https://github.com/retinapeg/agentic-physics-bench, local folder `~/Desktop/agentic-physics-bench`. V1 = tag `v1.0.0` (`8d336d8`) on `main`, immutable. A separate analytical proposal lives on the branch `research/analytical-physics` (unapproved, unrun; not part of this branch). **V2 (difficulty × tool policy) is on `v2/tool-policy`, exactly one commit on top of `main`** (rebuilt as a clean change set on 2026-09-23 at Leo's direction and rebased onto `1b0a819`, the merge of PR #2 that added the V1 architecture diagram; the first push, based on the research branch, is kept locally as `backup/v2-tool-policy-first-push`). The repository has been public since 19:33 BST on 2026-09-22 (recorded on the research branch); the inherited section's "Repo: private" is history.

Leo is the research lead and decision maker; Claude writes code, checks and documentation at his direction; Codex is the independent reviewer.

## V2 current state (2026-09-23)

- **V1: verified complete** (2026-09-23) in an isolated worktree of `v1.0.0`; the only present-day limitation is the installed CLI 2.1.280 vs the frozen 2.1.278. No V1 file changed. Entry: `RESEARCH_LOG.md` "V1 verification".
- **V2 implemented and development-calibrated; scored run NOT started.** Protocol draft `EXPERIMENT_V2.md` (decisions V2-1…V2-8 await Leo). Code `src/tasks_v2.py`, `agent_v2.py`, `run_v2.py`, `analyze_v2.py`, `chart_v2.py`; prompts `prompts/v2/`; data `data/v2/` (18 scored tasks in three groups, 162-episode seeded plan; 6 development tasks). V1's frozen files untouched (`git diff v1.0.0 -- src/tasks.py … data/` empty). 90 offline checks pass; CI workflow added.
- **Development calibration (final = stage 3 tool conditions + stage 4 no-tool):** no tool 6/6 with Leo's V2-4b wording ("No tools or code execution are available. Compute the answer from the table."; stage 3's earlier wording gave 2/2, 1/2, 0/2 with code-seeking replies, kept as a finding in `results/v2/dev_stage3/`); optional tool requested and executed 6/6, correct 6/6; required compliant 6/6, correct 6/6. The no-tool condition is at the ceiling on the six development tasks; grader, tolerance and tasks unchanged (Leo). `results/v2/summary_dev.md`, `chart_dev.svg`.
- **Frozen:** `data/v2/freeze_manifest.json`, run `v2-run-1`, 14:06:28 BST, 21 hashed files, CLI 2.1.280, effort high, 600 s timeout, `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1`; `verify_freeze` passes. Scored tasks/keys/plan hashes `201e8d39…` / `4c0189e1…` / `80da06fa…`, unchanged throughout.
- **PR #1 rebuilt as a clean `main` → V2 change set** (Leo's correction): one commit on top of `main` (`1b0a819`, which includes PR #2's architecture diagram; those two README sections are kept inside the V1 block); no `PROPOSAL.md`, `LINEAGE.md` or research-branch `CLAUDE.md`/docs changes; the research branch untouched; the first push kept locally as `backup/v2-tool-policy-first-push`.
- **Control failure found and fixed:** CLI 2.1.280 ran a server-side "advisor" (consulting `claude-fable-5-1`) inside 31/48 stage-1/2 calls under `--tools ""`. Stages 1–2 archived and void (`results/v2/dev_stage1/`, `dev_stage2/`, with audits); advisor disabled by `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1`; three new per-call violations. V1's 24 scored traces are unaffected (only `claude-opus-5`).
- **Reviews:** Codex (read-only, `gpt-6-astra`) found 3 executable defects; a 59-agent Claude review confirmed 14 findings (13 refuted). All fixed with regression tests. `results/raw/` remains gitignored; the tracked episode files are redacted of paths and identifiers at write time.
- **Codex as second evaluated system: deferred** (no tool-removal flag; live web search in config; served model not exposed).
- Local files (gitignored): `LEARNING_REVIEW.md` (one consolidated V2 entry, Q20–Q21), `APPLICATION_EVIDENCE.md` (for CV preparation).

## V2 timeline (2026-09-23; times BST, session clock)

| # | Time | Event | Done by | Evidence | Status |
|---|---|---|---|---|---|
| V1 | 11:36–11:52 | V1 audited in an isolated worktree of `v1.0.0`: 36 tests OK; data/analysis/chart byte-identical; 14 hashes match; `verify_freeze` fails on CLI version only (2.1.280 vs 2.1.278); saved episodes recounted and regraded; dispatch branch driven end to end with scripted replies; 1 live smoke call (controls hold; 7-day usage 20 %) | Claude, at Leo's direction | `RESEARCH_LOG.md` V1 verification entry; scratch worktree | VERIFIED |
| V2-1 | 11:47–11:57 | Branch `v2/tool-policy` from `9d12562`; groups designed with a shortcut simulation (4,000 draws per group); `tasks_v2.py`, prompts, `agent_v2.py`, `run_v2.py`, `analyze_v2.py`, `chart_v2.py`, 4 test files (73 checks with V1's); `EXPERIMENT_V2.md` with the development gate declared before any call | Claude | commit on the branch | VERIFIED (offline) |
| V2-2 | 11:58–12:24 | Development stage 1: 18 episodes, 36 calls, all valid under V1's controls; 18/18 correct; optional requests 0/2, 1/2, 2/2 by group; one fenced-JSON reply. Escalation to 60 points applied and wording revised (later reverted/kept, see V2-5) | Claude ran; pre-declared gate | `results/v2/dev_stage1/` | OBSERVED, later VOID for the gate |
| V2-3 | 12:04 | Codex review (`gpt-6-astra`; `gpt-6-sol` rejected on the ChatGPT account): 3 executable defects (resume replay, timeout hiding violations, integer overflow) | Codex found; Claude fixed with tests | `RESEARCH_LOG.md` stage-1 entry | VERIFIED |
| V2-4 | 12:26–12:40 | Development stage 2: six hard episodes at 60 points; 6/6 correct; optional requests 2/2 | Claude ran | `results/v2/dev_stage2/` | OBSERVED, later VOID |
| V2-5 | 12:40–12:48 | Multi-agent review completes: server-side advisor found in the raw traces (31/48 calls used `claude-fable-5-1`). Audits written; stages 1–2 declared void; escalation reverted (hard = 40); `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` plus three new per-call violations; probe confirms only `claude-opus-5` runs; ten further review findings fixed | Review found; Claude fixed | `advisor_audit.json` in both stage folders; `RESEARCH_LOG.md` control-failure entry | VERIFIED |
| V2-6 | 12:48–12:56 | Development stage 3 (clean): 36/36 calls `claude-opus-5` only; no tool 2/2, 1/2, 0/2; optional requested 6/6; required compliant 6/6; escalation not triggered | Claude ran | `results/v2/episodes_dev.jsonl`, `summary_dev.md`, `chart_dev.svg` | OBSERVED |
| V2-8 | 13:55–14:20 | Leo's corrections: (1) PR #1 to be a clean `main` → V2 change set; (2) V2-4b explicit no-tool sentence; rerun only the affected calibration; no grader/tolerance/task changes; no scored run until reported. Prompt changed (`no_tool_turn1.txt` SHA-256 `707bb945…`); `dev-restage stage3 --keep-unchanged --rerun-condition no_tool`; stage 4: no tool 6/6 (2/2, 2/2, 2/2), median thinking tokens 642 / 2,130 / 6,368 per call, hard calls 62 s median, 94 s max; freeze `v2-run-1` written at 14:06:28 before the stage-4 outcome; branch rebuilt on `main` and force-pushed with lease (first push kept locally); 90 checks OK; CI green | Leo decided; Claude implemented | `EXPERIMENT_V2.md` §9/§11; `RESEARCH_LOG.md` corrections and stage-4 entries; PR #1 | VERIFIED (hashes, `verify_freeze`, `git merge-base`) |
| V2-7 | 12:56–13:25 | Path redaction at write time (one stage-3 reply had quoted the CLI scratchpad path; file sanitised once); turn-1 reply classifier; end-to-end pipeline test; advisor-requested corrections (stage-1 archive note, gate outcome, tolerance simulation from the shipped generator, evidence-based approval request, decision V2-4b, V1 traces scanned for server-side tools); 90 checks OK; single squashed commit `0e4656f` pushed; PR #1 opened to `main` (https://github.com/retinapeg/agentic-physics-bench/pull/1) at 13:25 | Claude | this file; PR #1 | VERIFIED (push and PR URL) |

## V2 next action

**Waiting for Leo's go (the protocol is frozen; nothing scored has run).** Report delivered on 2026-09-23 at ~14:20: clean PR ancestry and diff; stage-4 no-tool results (6/6, ceiling on the development set); final frozen decisions V2-1…V2-8 with V2-4b as Leo decided; scored tasks, keys and plan unchanged. The scored run is 18 tasks × 3 conditions × 3 repetitions = 162 episodes, exactly 324 calls (the cap), one system: `claude-opus-5` via Claude Code 2.1.280, effort `high` (requested; unconfirmable from traces), advisor disabled. From the final development records (36 calls), the run needs about 1.2 M reported input tokens (mostly cache reads), 340 k output tokens and roughly 1.4 h, most of it in hard no-tool episodes (62 s median, 94 s max per call); usage windows after stage 4 were five-hour 51 % and seven-day 33 %, so it should start after the five-hour window has cooled. Fallback: repetition block 1 only (54 episodes, 108 calls, `--max-episodes 54`). On Leo's go, the manifest is already written, so only:

```bash
python3 src/run_v2.py scored-batch
```

The batch resumes after an interruption without repeating an episode and stops on any control violation, rate limit or three consecutive timeouts. After it: `python3 src/analyze_v2.py scored && python3 src/chart_v2.py scored`, fill the README's scored section, and merge the PR. Nothing in `main` changes until Leo merges PR #1 (https://github.com/retinapeg/agentic-physics-bench/pull/1).

---

# Inherited V1 handoff (history, unchanged below this line)

# Claude handoff — 2026-09-21 (last updated 19:48 BST)

Agentic Physics Bench is an AI engineering and research pilot. Leo is the research lead and decision maker; Claude writes the code and checks at his direction; Codex is the independent reviewer. Keep the project bounded: no extra agents or frameworks. Follow `CLAUDE.md` (its later standing instructions take precedence) and `WORKMODE.md`.

**Release naming (Leo, 19:45):** the pilot called "V0" in this file ships as **V1**, tag `v1.0.0`. Earlier rows keep their original wording.

**Active plan (Leo, 19:15):** resume implementation within the original five-hour work budget, without restarting the clock. This supersedes the stopping instruction of 18:45, which remains recorded in row 22. Continue through the delivery plan. Bring the remaining research decisions together for one protocol approval before any scored inference (`EXPERIMENT.md` section 13).

**Standing rules (Leo, 2026-09-21)**
- At the end of every checkpoint, update this file's timeline, current state and next action, and add a dated entry to `RESEARCH_LOG.md`. Cite evidence and say who did the work.
- Claude writes the functions and checks, runs them, and records actual results. Research decisions stay with Leo.
- Learning material lives only in the local, gitignored `LEARNING_REVIEW.md`, with one entry per completed checkpoint: concept → code → evidence → limitation → interview explanation. Leo will work through it on another day.
- The research direction is in `RESEARCH_ROADMAP.md`, which holds demonstrated results, hypotheses, three deferred follow-ups and source notes. It adds nothing to the V0 scope.

## Current state

- Repo: private (checked with `gh repo view`: `PRIVATE`). Checkpoint 1b is `94499d0`; checkpoint 2 is the next commit (see `git log`).
- Protocol: `EXPERIMENT.md` is **FROZEN** (19:30), commit `f504c57`, tag `v0-protocol-freeze`, with `data/freeze_manifest.json`. D1–D10 were approved with Leo's amendments.
- Code, all written by Claude at Leo's direction:
  - `src/tasks.py`: reference slope and dev cases.
  - `src/models.py`: Claude CLI adapter.
  - `src/evaluate.py`: parsers and grader.
  - `src/tools.py`: the allowlisted `fit_line` tool and request validation.
  - `src/agent.py`: the bounded loop (≤ 2 calls, ≤ 1 tool execution).
  - `src/run.py`: runs a direct or workflow dev episode and saves the trace (schema 2).
  - `prompts/`: direct, workflow turn-1 and workflow turn-2 templates.
- Tests: six test files, written by Claude, including regression tests for both defects Codex reproduced. 36 tests pass.
- Analysis: `src/analyze.py` produces `results/summary.json` and `.md`; `src/chart.py` produces `results/chart.svg`.
- Data: `data/dev_cases.jsonl` (what a model sees) and `data/dev_keys.jsonl` (answer key).
  - `dev_cases.jsonl` SHA-256 `07c79eb37ae2cfe0e45cbd6003aa1a049d4c30b02491bf5695604682fe8e4ef7`
  - `dev_keys.jsonl` SHA-256 `dfa56e5ab44f5be5fee284786f9bf128a57ee4d9049dd8e3e83ab141c3261059`
  - Scored cases: `data/scored_cases.jsonl`, `scored_keys.jsonl` and `scored_plan.json` (seed 202; hashes in the manifest).
- Episodes (dev-01, Claude, both correct), saved in `results/episodes_dev.jsonl`; raw output in `results/raw/`, which is gitignored:
  - direct: −1.9458 vs a_ref −1.945818 m/s²;
  - workflow: −1.946, answered **without requesting the tool** (1 call, 0 tool executions).
- **Scored pilot (19:31–19:35):** 24/24 episodes valid and correct; the tool was requested 0/12 times; 24 invocations. See `README.md`, `results/summary.md` and `results/chart.svg`.
- Research docs: `RESEARCH_ROADMAP.md`; `EXPERIMENT.md` section 11 (harness architecture) and section 12 (deterministic reference point).
- Publication: no public repo, release, or X post.

## Chronological timeline

All times are BST. Sources:
- "(mtime)" = file modification time: when the file was last written, not necessarily when the event happened.
- "(git)" = commit time.
- "(session)" = this Claude session, checked with `date`; a range means the exact minute wasn't captured.

| # | Time | Stage | Event | Done by | Evidence | Status |
|---|---|---|---|---|---|---|
| 1 | 11:28 (mtime) | Setup | Instruction files: CLAUDE, WORKMODE, AGENTS, RESEARCH_LOG | author not recorded | file times | OBSERVED |
| 2 | 11:41 (mtime) | 0 | Claude Code smoke test with `--tools ""`: answer "Newton", `model: claude-opus-5`, `tools: []` | Leo | `results/checkpoint0-claude.jsonl` (local, gitignored) | VERIFIED: trace reread in session |
| 3 | 11:59 (mtime) | 0 | GPT smoke test with `gpt-6-astra` requested: answer "newton", no tool events | Codex | `results/checkpoint0-codex.jsonl` (local, gitignored) | OBSERVED: served model ID unconfirmed |
| 4 | 11:59 (mtime) | 0 | Initial HANDOFF written; `.gitignore` excludes the smoke traces | Codex | file times | OBSERVED |
| 5 | 12:00 (git) | Setup | Commit `79c124f` and GitHub setup | Codex (git identity `retinapeg`) | `git log`; `origin/main` | OBSERVED |
| 6 | 12:54 (mtime) | 1a | Skeleton `EXPERIMENT.md` drafted, every parameter DECIDE | Claude, at Leo's request | file time | OBSERVED |
| 7 | before 13:31 (session) | 1a | Section 3 decided in chat. Sxx = 20.625 s² supplied by Codex, rechecked by Claude. The chat explanation was assistant-drafted. Claude's `tools: []` confirmed from the trace and `claude --help` | Leo decided; Codex computed; Claude checked | RESEARCH_LOG 1a entry | OBSERVED |
| 8 | 13:31 (session) | Process | Logging rule added to `CLAUDE.md`; log entries for checkpoints 0 and 1a; HANDOFF rewritten | Claude, directed by Leo | later commits | OBSERVED; attribution corrected in row 10 |
| 9 | 18:14 (session) | 1a | Section 3 values entered in `EXPERIMENT.md`, σ provisional | Claude, directed by Leo | `grep -n DECIDE EXPERIMENT.md` | OBSERVED: 1a gate passed for the recorded choices |
| 10 | 18:14 (session) | Process | Corrected attribution, timestamp labels and "reported input tokens" wording; learning review doc created | Claude, directed by Leo | RESEARCH_LOG correction entry | OBSERVED |
| 11 | 18:20–18:23 (session) | 1b | `ls_slope` walkthrough drafted as guidance, with a worked solution tested in a scratch folder outside the repo | Outline by Leo; text by Claude | local learning doc | OBSERVED |
| 12 | 18:23 (git) | 1a | Checkpoint 1a docs committed and pushed as `60fe171`. Scan for paths, emails and keys found nothing; traces not staged | Claude, directed by Leo | `git log`; `gh repo view` | OBSERVED |
| 13 | 18:31 (session) | Process | Verification and routine housekeeping handed to Claude | Leo decided; Claude recorded | `CLAUDE.md` | OBSERVED |
| 14 | 18:32 (git) | 1b | `tests/test_ls_slope.py` written and checked on scratch copies: correct → OK; endpoint slope → 2 failures; `sum/len` mean → 1 failure. Against the repo at the time: missing-module error, because `src/tasks.py` didn't exist. Committed as `d7e500a` | Claude | test output in session | OBSERVED |
| 15 | 18:34 (git) | Process | Learning review restructured as Leo's later-review workbook with catch-up tasks; `ce07160` | Leo decided; Claude restructured | `git log` | OBSERVED |
| 16 | 18:34–18:36 (session) | Process | Leo: "You write the functions"; learning deferred to another day | Leo decided; Claude recorded | `CLAUDE.md` | OBSERVED |
| 17 | 18:36 (session) | 1b | `src/tasks.py` and `tests/test_tasks.py` written; dev files generated. 9/9 tests OK; regenerating gives identical SHA-256s. dev-01 a_ref = −1.9458 m/s² (a_true −2.0942) | Claude, directed by Leo | unittest output; `shasum -a 256 data/*.jsonl`; RESEARCH_LOG 1b entry | VERIFIED |
| 18 | 18:36 (session) | Process | All learning material kept in one local doc, gitignored and untracked with `git rm --cached`. The repo is framed as an AI engineering and research project | Leo decided; Claude applied | `.gitignore` | OBSERVED |
| 19 | 18:40–18:44 (session) | 2 | Leo approved the prompt, the ±0.01 m/s² dev tolerance and the units ('go'). Claude wrote the prompt file, adapter, parser/grader and runner; 13 offline tests OK | Leo decided; Claude built | unittest output | OBSERVED |
| 20 | 18:44:57 (session) | 2 | Isolation probe (1 CLI call, answer 'ok'): `tools: []`, `mcp_servers: []`; still lists 21 skill names, 1 plugin, 5 built-in agents, but not the user's own skills; 4,570 reported input tokens | Claude, authorised by Leo | `results/raw/probe-isolation-*.json` (local) | OBSERVED |
| 21 | 18:45:26 (session) | 2 | dev-01 direct episode (1 CLI call, no retry): answer −1.9458 m/s², a_ref −1.945818, absolute error 1.8e-5 → correct; 0 tool uses; 3,862 in / 507 out reported tokens | Claude, authorised by Leo | `results/episodes_dev.jsonl` | VERIFIED (one dev episode) |
| 22 | 18:46–18:48 (session) | 2 | Leo set a firm stopping point. Rule changed to one learning entry per checkpoint. Docs updated; checkpoint 2 committed and pushed as `a9af5b1` | Leo decided; Claude applied | `git log` | OBSERVED |
| 23 | 19:01–19:12 (session) | Roadmap | Leo added a research-informed learning strand from an addendum Codex drafted in chat. Leo supplied it and directed adoption; drafter corrected at 19:15. Claude read 3 sources (abstract pages only for the preprints) and wrote `RESEARCH_ROADMAP.md`, `EXPERIMENT.md` sections 11–12 and the local learning sections. No model calls; `f5178fb` | Codex drafted; Leo directed; Claude wrote | `git log` | OBSERVED |
| 24 | 19:15 (session) | Process | Leo resumed implementation within the original five-hour budget, superseding the 18:45 stop (row 22). He set the tool-workflow design: case-ID request with harness-injected data, fresh-call turn 2, ≤ 2 calls, ≤ 1 tool execution, no retries | Leo decided | chat | OBSERVED |
| 25 | 19:15–19:17 (session) | 3 | `src/tools.py`, `src/agent.py`, workflow prompts, runner schema 2 and `tests/test_agent.py` written; 19/19 offline tests OK | Claude, directed by Leo | unittest output | VERIFIED (offline) |
| 26 | 19:17:01 (session) | 3 | dev-01 workflow episode (1 CLI call, no rerun): the model answered directly with −1.946 m/s² → correct; tool not requested; 0 tool executions | Claude, authorised by Leo | `results/episodes_dev.jsonl` line 2 | VERIFIED (one dev episode) |
| 27 | 19:18 (session) | 3 | Docs updated. `EXPERIMENT.md` section 13 now lists decisions D1–D10 for one approval. Checkpoint 3 committed and pushed as `224f18a` | Claude, directed by Leo | `git log` | OBSERVED |
| 28 | ~19:22 (session) | 4 | Leo approved D1–D10 with amendments (D3 no floor or redraw; D6 verify and pin effort; D7/D9 3 + 3 order within each sign group). Codex had reproduced two defects: a TypeError on `"name": []`, and `controls_ok=false` with `correct=true` | Leo decided; Codex reviewed | chat | OBSERVED |
| 29 | 19:26–19:29 (session) | 4 | Fixes plus regression tests; 34 offline tests OK. The regression tests fail on the old code: TypeError reproduced; old runner gave `controls_ok=False` and `correct=True` | Claude | unittest output; scratch run on `HEAD` code | VERIFIED |
| 30 | 19:27 (session) | 4 | Unplanned model call: `--effort bogus` was not rejected (stderr warning, default used, call made). Raw output not saved | Claude | stderr text in RESEARCH_LOG | OBSERVED |
| 31 | 19:30 (session) | 4 | Scored cases generated and validated; freeze manifest written; `EXPERIMENT.md` marked FROZEN; committed, tagged `v0-protocol-freeze` and pushed before any scored call | Claude, directed by Leo | `data/freeze_manifest.json`; tag | VERIFIED |
| 32 | 19:31 (git) | 4 | Freeze committed as `f504c57`, tagged `v0-protocol-freeze` and pushed | Claude, directed by Leo | `git log`; tag | VERIFIED |
| 33 | 19:31:35–19:34:38 (session) | 5 | Scored matrix: 24/24 valid and correct; tool requested 0/12; 24 invocations; stop reason `completed` | Claude, authorised by Leo | `results/episodes_scored.jsonl` | VERIFIED |
| 34 | 19:35–19:38 (session) | 5 | Analysis, chart, README and docs; 36 offline tests OK; freeze re-verified; checkpoint 5 committed and pushed | Claude, directed by Leo | `results/`; `README.md` | OBSERVED |
| 35 | ~19:45 (session) | Release | Leo: finish and ship V1 (the "V0" pilot) as `v1.0.0`, then create a derived project for numerical vs analytical performance | Leo decided | chat | OBSERVED |
| 36 | 19:48–19:48 (session) | Release | Clean-clone audit passed (36 tests; data and analysis reproduce byte for byte; freeze verified). README wording fix (where the CLI version is checked); V1 labels added. Committed, tagged `v1.0.0` and pushed | Claude, directed by Leo | `git show v1.0.0` | VERIFIED |

## Verified setup

- Apple M1 with 8 GB RAM. Python 3.11.5 (standard library only so far). No virtual environment.
- Claude Code 2.1.278 is signed in through a Claude subscription. The trace records one tool-free `claude-opus-5` response, with `apiKeySource: none`.
  - Overage was rejected (`org_level_disabled`). The trace reports the 7-day usage window at 65% at the time of the smoke test.
  - The trace's USD cost field is a list-price estimate, not a bill.
- Codex CLI 0.154.0 is signed in through ChatGPT. Codex JSONL does not show which model served the request, so record Astra as requested, not confirmed.
- Reported input tokens for one-word answers: Claude ≈ 4,605; Codex 16,297. How these split into instructions, tool definitions and other context is unverified. Neither trace records the prompt text or the command line.
- No provider API key is set. No local model runtime.

The raw smoke traces are gitignored because they contain session and machine metadata. Review every trace before publishing it.

## Open decisions and blockers

Items 1–4 from earlier versions (σ, tolerance, near-zero rule, workflow settings) were settled by the approval of D1–D10 (rows 24 and 28).
5. Claude CLI control: `--tools "" --safe-mode --strict-mcp-config --no-session-persistence --effort high`, in an empty temporary directory, with enforced checks (`src/run.py`). The init line still lists built-in skill names; whether they reach the model's context is unverified. The effort level is confirmed only by the absence of the fallback warning.
6. Codex/GPT: a read-only sandbox does not remove the shell tool. Choose prevention or detection (detection is weaker and must be labelled). Needs its own verification and approval before any GPT run.
7. H1 was not testable in V0 (tool requested 0/12, both conditions at ceiling). The next experiment needs a harder task or a design that separates tool choice from tool use (`RESEARCH_ROADMAP.md`).

## Release preparation (before making the repo public)

- `LEARNING_REVIEW.md` is untracked now but still in git history (commits `60fe171`, `d7e500a`, `ce07160`). Keeping it out of the public repo would need a history rewrite. That is Leo's decision; nothing has been done.
- `CLAUDE.md`, `WORKMODE.md` and `AGENTS.md` are assistant-instruction files with tutoring language. Decide whether to publish them as a record of how the project was built, or trim them.

## Next single action

The 18:45 stop (row 22) was superseded at 19:15 (row 24).

**Next action:** Phase 2. Create the derived project from the exact `v1.0.0` commit as a separate private repository. Write one matched numerical/analytical task example, a grading rubric and a small budget for Leo's research approval. Implement and run only after that approval.

**Release decisions (Leo, separate):** repository visibility; whether `LEARNING_REVIEW.md` must be removed from git history first; whether the assistant-instruction files stay public; any X post (draft kept locally).

Deferred: GPT/Codex, pending verified controls; follow-ups in `RESEARCH_ROADMAP.md`.

Delivery sequence (Leo, 2026-09-21):
1. A checked reference function and one reproducible dev case. **Done: rows 14 and 17.**
2. One real episode saved with its input, output, metadata and grade. **Done: rows 19–21.**
3. A bounded tool workflow on the same dev case. **Done: rows 25–26** (the model didn't request the tool).
4. A frozen protocol and scored dataset. **Done: rows 28–32.**
5. Direct and workflow runs on the same 12 scored cases. **Done: row 33.**
6. Analysis, one chart and a factual README. **Done: row 34.**

Claude first; add GPT once its controls are verified. No paid API calls or overage.

For later analysis: episode traces under `results/` are the data. This timeline and `RESEARCH_LOG.md` are the narrative index into them.
