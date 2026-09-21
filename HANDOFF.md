# Claude handoff — 2026-09-21 (last updated 19:18 BST)

Agentic Physics Bench is an AI engineering and research pilot. Leo is the research lead and decision maker; Claude writes the code and checks at his direction; Codex is the independent reviewer. Keep the project bounded: no extra agents or frameworks. Follow `CLAUDE.md` (its later standing instructions take precedence) and `WORKMODE.md`.

**Active plan (Leo, 19:15):** resume implementation within the original five-hour work budget, without restarting the clock. This supersedes the stopping instruction of 18:45, which remains recorded in row 22. Continue through the delivery plan. Bring the remaining research decisions together for one protocol approval before any scored inference (`EXPERIMENT.md` section 13).

**Standing rules (Leo, 2026-09-21)**
- At the end of every checkpoint, update this file's timeline, current state and next action, and add a dated entry to `RESEARCH_LOG.md`. Cite evidence and say who did the work.
- Claude writes the functions and checks, runs them, and records actual results. Research decisions stay with Leo.
- Learning material lives only in the local, gitignored `LEARNING_REVIEW.md`, with one entry per completed checkpoint: concept → code → evidence → limitation → interview explanation. Leo will work through it on another day.
- The research direction is in `RESEARCH_ROADMAP.md`, which holds demonstrated results, hypotheses, three deferred follow-ups and source notes. It adds nothing to the V0 scope.

## Current state

- Repo: private (checked with `gh repo view`: `PRIVATE`). Checkpoint 1b is `94499d0`; checkpoint 2 is the next commit (see `git log`).
- Protocol: `EXPERIMENT.md` is DRAFT and not frozen. σ = 0.5 m/s is provisional for development. Still open: final σ, tolerance, |a_true| floor or redraw rule, and sections 5–7.
- Code, all written by Claude at Leo's direction:
  - `src/tasks.py`: reference slope and dev cases.
  - `src/models.py`: Claude CLI adapter.
  - `src/evaluate.py`: parsers and grader.
  - `src/tools.py`: the allowlisted `fit_line` tool and request validation.
  - `src/agent.py`: the bounded loop (≤ 2 calls, ≤ 1 tool execution).
  - `src/run.py`: runs a direct or workflow dev episode and saves the trace (schema 2).
  - `prompts/`: direct, workflow turn-1 and workflow turn-2 templates.
- Tests: `tests/test_ls_slope.py`, `test_tasks.py`, `test_evaluate.py` and `test_agent.py`, written by Claude. 19 tests pass.
- Data: `data/dev_cases.jsonl` (what a model sees) and `data/dev_keys.jsonl` (answer key).
  - `dev_cases.jsonl` SHA-256 `07c79eb37ae2cfe0e45cbd6003aa1a049d4c30b02491bf5695604682fe8e4ef7`
  - `dev_keys.jsonl` SHA-256 `dfa56e5ab44f5be5fee284786f9bf128a57ee4d9049dd8e3e83ab141c3261059`
  - Scored cases are not generated.
- Episodes (dev-01, Claude, both correct), saved in `results/episodes_dev.jsonl`; raw output in `results/raw/`, which is gitignored:
  - direct: −1.9458 vs a_ref −1.945818 m/s²;
  - workflow: −1.946, answered **without requesting the tool** (1 call, 0 tool executions).
  - No scored cases or scores.
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
| 27 | 19:18–19:18 (session) | 3 | Docs updated. `EXPERIMENT.md` section 13 now lists decisions D1–D10 for one approval. Checkpoint 3 committed and pushed | Claude, directed by Leo | `git log` | OBSERVED |

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

1. Final σ and the tolerance rule: can a least-squares fit be told apart from shortcuts such as the endpoint slope within the tolerance?
2. A minimum |a_true| or a redraw rule, decided before scored generation.
3. The remaining decisions are collected as D1–D10 in `EXPERIMENT.md` section 13 for one approval: σ, tolerance, near-zero redraw, workflow wording, transport failures, effort level, run order, systems, sign order and invalid tool requests.
4. (Settled at 19:15: tool arguments are injected by case ID; turn 2 is a fresh call; no retries.)
5. Claude CLI control: episodes run in an empty temporary directory with `--tools "" --safe-mode --strict-mcp-config --no-session-persistence`. The runner logs the command line and prompt. The init line still lists built-in skill names; whether they reach the model's context is unverified. The effort level is not pinned.
6. Codex: a read-only sandbox does not remove the shell tool. Choose prevention or detection; detection is a weaker control and must be labelled as such. This blocks Codex episodes only.

## Release preparation (before making the repo public)

- `LEARNING_REVIEW.md` is untracked now but still in git history (commits `60fe171`, `d7e500a`, `ce07160`). Keeping it out of the public repo would need a history rewrite. That is Leo's decision; nothing has been done.
- `CLAUDE.md`, `WORKMODE.md` and `AGENTS.md` are assistant-instruction files with tutoring language. Decide whether to publish them as a record of how the project was built, or trim them.

## Next single action

The 18:45 stop (row 22) was superseded at 19:15 (row 24).

**Next action:** Leo approves or edits decisions D1–D10 in `EXPERIMENT.md` section 13, in one pass. Then Claude:
1. implements any changes (e.g. the near-zero redraw) and confirms by hash that the dev files are unchanged;
2. generates the 12 scored cases (seed 202), fills in the freeze record and commits it;
3. runs the 24 scored episodes on Claude (at most 36 CLI calls);
4. analyses the saved results.
No scored inference before that approval.

Delivery sequence (Leo, 2026-09-21):
1. A checked reference function and one reproducible dev case. **Done: rows 14 and 17.**
2. One real episode saved with its input, output, metadata and grade. **Done: rows 19–21.**
3. A bounded tool workflow on the same dev case. **Done: rows 25–26** (the model didn't request the tool).
4. A frozen protocol and scored dataset.
5. Direct and workflow runs on the same 12 scored cases.
6. Analysis, one chart and a factual README.

Claude first; add GPT once its controls are verified. No paid API calls or overage.

For later analysis: episode traces under `results/` are the data. This timeline and `RESEARCH_LOG.md` are the narrative index into them.
