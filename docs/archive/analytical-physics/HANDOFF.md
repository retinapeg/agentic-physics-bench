# Handoff: research branch `research/analytical-physics` (last updated 19:35 BST, 2026-09-22)

**Canonical paths (Leo's one-repo decision, 2026-09-22 ~00:37):**
- Repository: https://github.com/retinapeg/agentic-physics-bench. Local folder: `~/Desktop/agentic-physics-bench`.
- V1: tag `v1.0.0` (`8d336d8`) on `main`, immutable.
- Study work: the branch `research/analytical-physics`.
- The separate repository `retinapeg/agentic-physics-bench-analytic` and its folder are **superseded**: preserved, not deleted, not rewritten, not used. See `LINEAGE.md`.

Leo is the research lead and decision maker; Claude writes code and documentation at his direction; Codex is the independent reviewer and, overnight on 2026-09-22, the coordinator and tutor, with Leo's authorisation. The V1 standing rules carry over.

## Current state

- Branch `research/analytical-physics`: starts at `v1.0.0`. It contains commit `955b3b2` (lineage and proposal, originally pushed to the superseded repository) and the consolidation and documentation commits after it.
- Proposal: `PROPOSAL.md` gives the matched example, the rubric, a budget of ≤ 80 CLI calls and decisions P1–P8. It **awaits Leo's research approval.** Recommended revisions are in `RESEARCH_ROADMAP.md` and are recommendations only.
- Code: V1's, unchanged. No new tools, tasks, installs or model calls.
- **Visibility: the repository is PUBLIC** since 19:33 BST on 2026-09-22 (Leo's decision, after a pre-publication audit; see row D10 and the release entry in `RESEARCH_LOG.md`). Both `main` and `research/analytical-physics` are visible, with the tags `v1.0.0` and `v0-protocol-freeze`. The superseded `retinapeg/agentic-physics-bench-analytic` stays private. The "Repo: private" line in the inherited V1 section below is history and is superseded by this line.
- Learning workbook: the local, gitignored `LEARNING_REVIEW.md` in the canonical folder. It is the single continuing workbook; start with its **START HERE** section. It holds the newest merged content, and no attempts are recorded yet.

## Timeline (research branch)

| # | Time | Event | Done by | Evidence | Status |
|---|---|---|---|---|---|
| D1 | ~19:45 (09-21, session) | Leo: after V1 ships, start a follow-up study on numerical vs analytical performance with a bounded math-tool harness | Leo decided | chat | OBSERVED |
| D2 | 19:50 (09-21, session) | Separate repository cloned from `v1.0.0`, with history and tags kept; the workbook copied locally | Claude, directed by Leo | superseded repo; `LINEAGE.md` | VERIFIED |
| D3 | 19:51 (09-21, session) | `PROPOSAL.md` written. Example references checked: closed form vs finite differences 8 × 10⁻¹²; symbolic reference vs finite differences at 25 points ≤ 2.8 × 10⁻¹⁰ | Claude | `PROPOSAL.md` | OBSERVED |
| D4 | 19:52 (09-21, session) | Commit `955b3b2` pushed to the separate private repository | Claude, directed by Leo | `git log` | OBSERVED |
| D5 | 00:35–00:37 (09-22, session) | Overnight documentation pack started in the separate folder (START HERE and chronology in the local workbook). Codex coordinated, on Leo's authorisation | Claude | local workbook | OBSERVED |
| D6 | ~00:37 (09-22) | Leo's one-repo decision, relayed by Codex; the separate repository superseded | Leo decided | chat | OBSERVED |
| D7 | 00:37–00:39 (09-22, session) | Both folders inspected (clean, no stashes, no attempts). Both workbooks backed up. Branch created in the canonical repo from `955b3b2`, which sits directly on `v1.0.0`. The newest workbook merged into the canonical folder. Lineage, README, CLAUDE.md and this file updated | Claude | `git log research/analytical-physics` | VERIFIED |
| D8 | 00:39–00:42 (09-22, session) | Overnight documentation pack in the canonical folder. Local workbook: START HERE, chronology, findings and limits, architecture, pending study, questions capped at two per checkpoint, interview accounts. Tracked: `RESEARCH_ROADMAP.md` pending-study notes and R1–R5 (recommendations only), a clarification entry in `RESEARCH_LOG.md`, this row. Offline checks only | Claude; coordinated by Codex; authorised by Leo | branch commits; local workbook | OBSERVED |
| D9 | 00:48 (09-22, session) | Four wording corrections from Codex's documentation verification: attribution in the interview scripts; qualified binomial intervals (0.265 is a two-sided endpoint; one-sided 0.221); the stale roadmap line and historical headings; derivation vs formulation. Documentation only | Claude; issues found by Codex | `RESEARCH_LOG.md` correction entry | OBSERVED |
| D10 | 19:20–19:33 (09-22, session) | Pre-publication audit of every ref and all history: no credentials, identifiers, absolute paths or machine metadata; traces sanitised; no stashes or dangling objects; `git diff v1.0.0 HEAD -- src tests data results` empty. `LEARNING_REVIEW.md` found in history in three versions and accepted, because purging it would rewrite `v1.0.0` and `v0-protocol-freeze`. Leo chose publish-as-is and both branches. `gh repo edit --visibility public` run; `gh repo view` confirms `PUBLIC` | Audit and action by Claude; both decisions by Leo | `RESEARCH_LOG.md` release entry; `gh repo view --json visibility` | VERIFIED |

## Open review request for Codex (2026-09-22)

Read-only independent review of V1 (released) and the state of the `research/analytical-physics` branch. Written by Claude at Leo's request so both assistants work from the same brief. Use the AGENTS.md output format, cap at **three findings**, and add the extra section named in item D.

**Scope:** commits `8d336d8` (tag `v1.0.0`) and the branch through its latest commit. Read-only: no model calls, no new experiments, no edits to tracked files, no approval of P1–P8 (Leo's decision alone).

**Offline commands available to you (none call a model):**
- `python3 -m unittest tests.test_ls_slope tests.test_tasks tests.test_evaluate tests.test_agent tests.test_controls tests.test_analyze`
- `python3 src/tasks.py && python3 src/tasks.py scored && git status --short data/` (expect no changes)
- `python3 src/analyze.py && python3 src/chart.py && git status --short results/` (expect no changes)
- `python3 -c "import sys; sys.path.insert(0,'src'); import run; run.verify_freeze()"`

**A. Claim audit.** Does every quantitative claim in `README.md`, `RESEARCH_LOG.md` and `RESEARCH_ROADMAP.md` follow from `results/episodes_scored.jsonl` and `results/summary.json`? Check in particular: 12/12 in each condition; tool requested 0/12; "every answer equals the reference rounded to 1–6 decimals"; 24 invocations; the byte-identical reproduction claims.

**B. Validity of the harness as an eval.** Is there any path where a control violation, a missing output or an unattempted episode could still be graded correct or silently leave the denominator? Check `control_violations`, `make_model_caller`, `run_batch` and `summarize`. Is the strict-JSON, no-repair rule actually enforced? Can an answer key reach the model through the prompt, the tool or the working directory?

**C. Freeze integrity.** Was anything covered by `data/freeze_manifest.json` modified after the freeze commit `f504c57`? Does the tag still resolve to `8d336d8`? Does `verify_freeze` cover what the README says it covers (it checks the CLI version once before a batch, not per call)?

**D. Extra section: research reading.** Leo's open question is whether the saved results contain a defensible AI-research finding or only a ceiling artefact. Name **at most two** candidate findings. For each: the exact evidence, the strongest reason it might be an artefact of this design, and the smallest additional check that would separate the two. Do not propose a new study.

**E. Statistical wording.** Tonight's docs describe the 12/12 and 0-discordant intervals as illustrative exact binomial intervals with stated assumptions (see the correction entry in `RESEARCH_LOG.md`). Is that stated correctly and consistently, and is any unconditional accuracy claim left anywhere?

**F. State of the branch.** Is `LINEAGE.md` accurate about the superseded repository? Is authorship recorded correctly throughout (Leo decided, Claude implemented, Codex reviewed)? Does `PROPOSAL.md` overclaim anything, given it is unapproved?

## Next action

1. **V1's results still need Leo's own reading (2026-09-22).** The engineering is released and tagged, but the research interpretation is *not* finished: Leo has yet to go through the saved results and decide whether anything in them is an interesting AI-research finding. Until he has, "V1 is done" means the build shipped, not that the pilot has been interpreted. Evidence to read: `results/summary.md`, `results/episodes_scored.jsonl`, `results/chart.svg`, and the failure review in `README.md`.
2. Leo approves or edits P1–P8 in `PROPOSAL.md`, including whether to install SymPy (P6), and reads the recommendations in `RESEARCH_ROADMAP.md` first. Nothing needing approval is started before then.

The analytical branch continues in parallel, but item 1 belongs to V1 and doesn't wait on it.

**Release decisions: visibility is now settled (public, 19:33 BST 2026-09-22).** Still open and still Leo's: whether the assistant-instruction files (`CLAUDE.md`, `WORKMODE.md`, `AGENTS.md`) stay published as a record of how the project was built or get trimmed; and whether to make any public post. The history question is closed: `LEARNING_REVIEW.md` stays in history, because removing it would rewrite the release tags.

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
