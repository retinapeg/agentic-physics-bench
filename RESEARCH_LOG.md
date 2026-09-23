# AI research and engineering lessons

Append-only. Short evidence-backed entries, not copied chat transcripts. No medical details, private messages, credentials or employer data belong in the public log.

## Evidence status

PLANNED: not attempted.
OBSERVED: output or artifact exists; interpretation may still be uncertain.
VERIFIED: a named check reproduced the relevant result.
HYPOTHESIS: a possible explanation, not established fact.

Do not change an old mistaken claim silently. Add a dated correction with the new evidence.

## Entry template

### YYYY-MM-DD | checkpoint | short title
- Concept:
- What I expected:
- What I did / observed:
- Evidence: command + result, test name, file/line, commit, or run ID.
- Failure type and suspected cause, when applicable:
- Change and verification:
- Lesson in my own words:
- Status: PLANNED / OBSERVED / VERIFIED / HYPOTHESIS.
- Next experiment or remaining uncertainty:

Keep ordinary entries to five to eight lines; combine fields when possible.

## 2026-09-21 | Design | Separate expectation from evidence
- Concept: a hypothesis is not a measured result.
- What I expect: tools may reduce the open/frontier performance gap.
- Plan: freeze a small physics set and compare direct and bounded-tool conditions.
- Evidence: none yet; this starter pack contains no evaluated episodes.
- Lesson: publish the observed counts even if the hypothesis fails.
- Status: PLANNED.

## 2026-09-21 | 0 Environment | One-word answers, thousands of reported input tokens
- Authorship: Claude drafted this entry at 13:31 BST from the saved traces, after the smoke tests. Leo ran the Claude smoke test. Codex ran the GPT smoke test.
- Concept: a subscription CLI is an agent system (the model plus whatever instructions, tool definitions and context the CLI adds), not a bare model. Model identity has to come from provider metadata.
- Observed, Claude: Claude Code 2.1.278, run with `--tools ""` (per Leo). Trace init line: `model: claude-opus-5`, `tools: []`, `mcp_servers: []`, `apiKeySource: none`. Answer "Newton"; 1 turn; 1.66 s. Overage was rejected (`org_level_disabled`). The trace reports the 7-day usage window at 65% utilisation (trace file modified 11:41).
- Observed, Codex: Codex CLI 0.154.0, `gpt-6-astra` requested. Answer "newton"; no tool events. The JSONL has no field for the model that actually served the request.
- Reported input tokens: Claude 2 + 3,162 cache-write + 1,441 cache-read ≈ 4,605. Codex 16,297 (6,400 cached). How these split into hidden instructions, tool definitions and other context is unverified. Neither trace records the prompt text or the command line.
- Evidence: `results/checkpoint0-claude.jsonl` lines 0–3; `results/checkpoint0-codex.jsonl` `turn.completed.usage`. Both are gitignored and exist only on this machine.
- Lesson (Leo): TODO
- Status: OBSERVED. Why Codex reports about 3.5× Claude's input tokens is unknown. HYPOTHESIS: tool definitions and/or an AGENTS.md read from the working directory.

## 2026-09-21 | 1a Protocol | Grade the fit of the displayed data, not the generator
- Concept: reference answers and leakage. The answer key must depend only on what the model sees.
- Did: at Leo's request, Claude drafted a skeleton `EXPERIMENT.md` (DRAFT, untracked, every parameter marked DECIDE). Leo decided the section 3 parameters in chat:
  - seeds 101 (dev) and 202 (scored); N = 10; t = 0–4.5 s in 0.5 s steps;
  - `a_true` continuous in ±(0, 5] m/s², sign-balanced: 2+/2− dev, 6+/6− scored; v0 uniform in [−10, 10] m/s;
  - velocities shown to 2 decimal places, with the reference computed from the displayed values.
  - σ, the tolerance, and sections 5–7 are still open.
- Evidence: Sxx = 20.625 s² (supplied by Codex; Claude reran it in python3), so SD(a_ref about a_true) = σ/√20.625 ≈ 0.22σ. At the 1a check, `grep -n DECIDE EXPERIMENT.md` still showed all 7 section 3 rows as DECIDE, so the gate had not passed.
- Review notes (Claude):
  - Balancing the sign of `a_true` does not fix the sign of `a_ref` near zero. This needs a minimum |a_true| or a redraw rule.
  - The σ/tolerance check should be least-squares versus cheap shortcuts such as the endpoint slope, not guessing `a_true`. Leo's pushback on this was accepted.
- Explanation submitted in chat, assistant-drafted per Leo's correction (not independently written by Leo): "We should grade against `a_ref` because the model is asked to fit the displayed measurements. Noise and rounding can make that slope differ from `a_true`, so using `a_true` could mark a correct fit as incorrect."
- Lesson (Leo, own words): TODO (see LEARNING_REVIEW.md Q2).
- Status: OBSERVED (design decisions only; nothing measured). Codex tool control is unresolved: a read-only sandbox does not disable its tools.

## 2026-09-21 | Correction | Attribution, timestamps and token wording
- Recorded 18:14 BST by Claude at Leo's direction. Earlier text in the two entries above and in HANDOFF.md was fixed in place, because it was written earlier today (13:31) and never committed. This entry records what changed.
- Attribution:
  - Codex, not Leo, ran the GPT smoke test and did the initial HANDOFF, commit and GitHub setup.
  - Leo ran the Claude smoke test.
  - Codex supplied Sxx = 20.625 s²; Claude checked it. The earlier text said Leo derived it.
  - The 1a explanation was assistant-drafted; the earlier text presented it as Leo's own words.
- Timestamps taken from file modification times are now labelled "(mtime)". The git commit time is labelled "(git)".
- Token figures are now "reported input tokens". The earlier "hidden context/tokens" wording claimed a breakdown nobody has verified.
- Status: VERIFIED against Leo's statement in chat; no trace records who ran each command.

## 2026-09-21 | 1a Protocol | Section 3 recorded in the file
- Authorship: decisions by Leo; entered into `EXPERIMENT.md` by Claude at Leo's direction.
- Observed: all six choices are in the section 3 table. σ = 0.5 m/s is marked PROVISIONAL (development only). Two rows still contain DECIDE: the final σ and the minimum |a_true| or redraw rule. The protocol remains DRAFT.
- Evidence: `grep -n DECIDE EXPERIMENT.md` after the edit.
- Also: Claude drafted `LEARNING_REVIEW.md` (questions, marking scheme, tutor instructions) at Leo's request. Comprehension questions now live there; working-code checks stay in the checkpoints.
- Status: OBSERVED. 1a gate passed for the recorded choices; final σ, tolerance and the |a| floor are open.

## 2026-09-21 | 1b Ground truth | Reference function and reproducible dev cases
- Authorship: around 18:35 BST Leo handed the implementation to Claude ("You write the functions") and deferred his learning tasks. Claude wrote everything in `src/tasks.py` (`ls_slope`, `make_case`, `make_dev_cases`) and both test files. None of `src/` is Leo's code.
- Earlier failure, preserved: before `src/tasks.py` existed, `tests.test_ls_slope` stopped with a missing-module error (HANDOFF row 14).
- Observed: `python3 -m unittest tests.test_ls_slope tests.test_tasks` gives 9 tests, OK. For every dev case, `a_ref` matches both `statistics.linear_regression` and an exact fraction calculation from the displayed strings, to 12 decimal places.
- Reproducibility: two generator runs gave identical files on Python 3.11.5. `dev_cases.jsonl` SHA-256 = 07c79eb3…4ef7; `dev_keys.jsonl` SHA-256 = dfa56e5a…1059.
- Dev references, a_ref (a_true), in m/s²: dev-01 −1.9458 (−2.0942); dev-02 +4.5381 (+4.6482); dev-03 −4.3033 (−4.4460); dev-04 +2.3088 (+2.3246). The signs of `a_ref` and `a_true` agree in all four.
- Process: all learning material is now in the local, gitignored `LEARNING_REVIEW.md`. Earlier references to it in this log point to that local file.
- Lesson (Leo): TODO
- Status: VERIFIED by the named checks. σ is still provisional; scored cases have not been generated.

## 2026-09-21 | 2 Episode | One real direct episode on dev-01, saved and graded
- Authorship: Claude wrote `prompts/direct.txt`, `src/models.py`, `src/evaluate.py`, `src/run.py` and `tests/test_evaluate.py` at Leo's direction. Leo approved the prompt wording, the provisional dev tolerance (±0.01 m/s²) and the accepted units ("go"). Claude made both CLI calls with Leo's authorisation.
- Isolation probe (18:44:57, 1 call, answer "ok"):
  - With `--safe-mode --tools ""`, the init line shows `tools: []` and `mcp_servers: []`.
  - It still lists 21 skill names, 1 plugin (`pyright-lsp`) and 5 built-in agents, but none of the user's own skill folders.
  - With no tools these can't be invoked. Whether their names reach the model's context is unverified.
  - Reported input tokens: 4,570.
- Episode dev-01 direct (18:45:26, 1 call, no retry):
  - Response `{"type": "final", "acceleration": -1.9458, "units": "m/s^2"}`. a_ref = −1.945818 m/s²; absolute error 1.8 × 10⁻⁵; **correct** at the provisional tolerance.
  - Init `tools: []`, 0 tool-use blocks, 1 turn, 8.3 s.
  - Reported 3,862 input and 507 output tokens; a `thinking` block came before the text.
  - Overage was rejected and not used.
- Evidence: `results/episodes_dev.jsonl` (reviewed summary, committed); `results/raw/` (full CLI output, local, gitignored). 13 offline tests OK. Prompt SHA-256 `c4e2f47f…74f3`.
- Lesson (Leo): TODO
- Status: VERIFIED for one development episode. This is not an accuracy estimate. The effort level isn't pinned. Why the probe and the episode report different input-token totals (4,570 vs 3,862) is unexplained.

## 2026-09-21 | Roadmap | Research direction recorded; no new experiment
- Authorship: Leo supplied a brief adding a research-informed learning strand; its drafter is not recorded here. Claude wrote `RESEARCH_ROADMAP.md` and `EXPERIMENT.md` sections 11–12 at Leo's direction.
- Did: read the three suggested sources: one Anthropic engineering post, and two arXiv abstract pages (not the full papers). Recorded each source's claim, what it actually evaluated, a limitation and its relevance. Confirmed titles, authors and dates from the arXiv pages.
- Correction to the brief: the harness-evolution abstract names neither the fixed model nor any effect sizes. The roadmap says so.
- Scope: V0 is unchanged (4 dev cases, 12 scored cases). Follow-ups 1–3 and "harness debt" are deferred; novelty is not established. Nothing has been reproduced.
- Status: OBSERVED (documentation only; no model calls).

## 2026-09-21 | Correction | Drafter of the research addendum
- Recorded 19:18 BST by Claude at Leo's direction. The roadmap entry above said the brief's drafter was "not recorded". In fact Codex drafted the research addendum in chat, and Leo supplied it and directed its adoption. `RESEARCH_ROADMAP.md` and `HANDOFF.md` row 23 now say so.
- Status: VERIFIED against Leo's statement in chat.

## 2026-09-21 | 3 Tool workflow | Bounded fit_line workflow built; the model did not request the tool
- Authorship:
  - Leo decided the design: the model names the case ID and the harness injects the displayed data; turn 2 is a fresh call with the original task, the previous public reply and the tool result; at most 2 model calls and 1 tool execution; no retries.
  - Claude wrote `src/tools.py`, `src/agent.py`, the workflow prompts, the runner changes and `tests/test_agent.py`. Ending on an invalid tool request was Claude's choice (for approval).
- Offline: 19 tests OK. Scripted replies cover tool then answer; answer without the tool; three invalid requests, none executed; a second tool request (`tool_limit_exceeded`); and malformed or missing replies. They also check that the turn-2 prompt holds the task, the previous reply and the tool result, and no template variables.
- Real episode, dev-01 workflow (19:17:01, 1 call, no rerun):
  - The model answered directly: `{"type": "final", "acceleration": -1.946, "units": "m/s^2"}`.
  - Absolute error 1.8 × 10⁻⁴ m/s²; **correct**; 0 tool executions.
  - Controls OK; 477 output tokens reported.
- Measurement limit: reported input-token totals don't track prompt length (direct 3,862; workflow 3,863 with a prompt about twice as long; probe 4,570). Unexplained; not used as evidence.
- Design consequence: `fit_line` returns exactly `a_ref`, so tool use plus faithful relaying guarantees a correct answer. With optional wording, the workflow tests whether the system chooses the tool. This is decision D4 in `EXPERIMENT.md` section 13.
- Lesson (Leo): TODO
- Status: VERIFIED for the workflow's control logic (offline) and one dev episode (n = 1, tool not used). No tool benefit is demonstrated.

## 2026-09-21 | 4 Review and freeze | Two reproduced defects fixed; protocol frozen
- Authorship: Codex independently reproduced both defects. Leo approved D1–D10 with amendments (D3: no floor or redraw; D6: verify and pin effort; D7/D9: 3 + 3 condition order within each sign group). Claude implemented and verified the fixes and the freeze.
- Defect 1: a tool request with `"name": []` crashed `validate_request` (TypeError: unhashable type). The fix checks field types before the allowlist lookup; tool exceptions also become a recorded `tool_error`. The regression test raises the same TypeError on the previous commit's code and passes on the fix.
- Defect 2: the old runner could record `controls_ok = false` together with `grade.correct = true`; reproduced with a scripted call listing a native `Bash` tool. The new runner validates:
  - required initialization metadata;
  - `tools: []` and `mcp_servers: []`;
  - the model ID;
  - no native tool use, no overage, no stderr output.

  Any violation makes the episode `invalid_run`: it is not graded, its evidence is preserved, and the batch stops. 34 offline tests pass.
- Effort check (19:27): `--effort bogus` was **not** rejected. The CLI warned on stderr, used the default and made a model call. That was one unplanned invocation outside the matrix; its raw output was not saved. `high` is pinned and stderr is now a control.
- Freeze (19:30):
  - 12 scored cases (seed 202). References validated by `statistics.linear_regression` and exact fractions; byte-identical on regeneration.
  - Signs −+ interleaved, 6/6. No `a_ref`/`a_true` sign disagreements. Smallest |a_ref| 0.965 m/s².
  - `data/freeze_manifest.json` hashes 14 files and records the CLI version and arguments. The runner refuses scored inference if any of these differ.
- Lesson (Leo): TODO
- Status: VERIFIED (offline checks, regression reproduction, hashes). No scored inference before the freeze commit.

## 2026-09-21 | 5 Scored pilot | 24/24 correct; the optional tool was never requested
- Authorship: Claude ran the approved, frozen matrix (19:31:35–19:34:38 BST) and wrote `src/analyze.py`, `src/chart.py`, `tests/test_analyze.py` and `README.md` at Leo's direction.
- Observed:
  - All 24 planned episodes were attempted and valid, using 24 invocations (cap 36). No stderr, overage or control violations. Model `claude-opus-5`, CLI 2.1.278 throughout; all rate-limit statuses "allowed".
  - Direct 12/12 and workflow 12/12 correct; paired: 12 ties. The tool was requested 0/12 times.
  - Absolute error, median / max: direct 1.1e-4 / 4.5e-4; workflow 2.1e-4 / 1.5e-3 m/s². Every answer equals `a_ref` rounded to between 1 and 6 decimals.
  - The deterministic solver scores 12/12 with zero error.
- Failure review: no model errors. The failures examined are the two harness defects found in review (checkpoint 4) and the ignored `--effort` value. The closest scored case is s-07 workflow (−3.6 vs −3.601455).
- Interpretation: a ceiling result. The pilot shows the system reproduces a least-squares slope to within rounding on this task. It cannot show a tool effect, because the tool was never used. No claim of significance, ranking or tool benefit is made.
- Evidence: `results/episodes_scored.jsonl`, `results/summary.json` and `.md`, `results/chart.svg`; 36 offline tests OK; the freeze manifest was verified before and after the run.
- Lesson (Leo): TODO
- Status: VERIFIED (deterministic recount matches; frozen files unchanged).

## 2026-09-21 | Release | V1 shipped as v1.0.0
- Naming: per Leo, the finished pilot (called "V0" in the entries above) is released as **V1**, tag `v1.0.0`. The earlier entries are unchanged.
- Release audit (19:48 BST, by Claude): on a fresh clone from GitHub, 36 offline checks pass; regenerating the data leaves every file unchanged; `analyze.py` and `chart.py` reproduce the committed results byte for byte; `verify_freeze` passes.
- Documentation fix before tagging: the README said the CLI version is checked per call. It is checked once before the batch (freeze verification); per call, only its presence is checked. No code change; frozen files untouched.
- Scope: unchanged from checkpoint 5. No RAG, memory, symbolic tools, other task families or other models.
- Status: VERIFIED (release audit). Repo visibility and social posting are Leo's separate decisions; nothing published.

## 2026-09-21 | Derived project | Created from V1 v1.0.0; proposal awaiting approval
- Authorship: Leo decided to create the derived project and set its questions. Claude created the repository and wrote `LINEAGE.md` and `PROPOSAL.md`.
- Lineage: parent `retinapeg/agentic-physics-bench`, tag `v1.0.0`, commit `8d336d8302ecf76b6bcabf7afc37ab817a0630ea`. The history and tags are kept, and the parent remote is fetch-only.
- Observed: the example's references checked two ways. The closed form vs a central finite difference agree to 8 × 10⁻¹² (v(0.37 s) = −0.4093 m/s). The symbolic derivative vs finite differences at 25 random points gives worst scaled error 2.8 × 10⁻¹⁰.
- Status: PLANNED (study). No new model calls in this project.

## 2026-09-22 | Consolidation | One canonical repository; research branch
- Decision (Leo, relayed by Codex, ~00:37): "I don't want multiple repos having multiple versions of a project." All work continues in `retinapeg/agentic-physics-bench`. V1 stays the immutable tag `v1.0.0` on `main`; the study goes on the branch `research/analytical-physics`.
- Done by Claude (00:38): the branch starts from commit `955b3b2`, fetched from the now-superseded separate repository, so the lineage/proposal commit keeps its hash and authorship. Its parent is exactly `v1.0.0` (`8d336d8`), and the tag was not moved. The separate repository and folder are preserved, not deleted or rewritten, and no longer used. The local workbooks were compared: the canonical copy was a strict subset, with no attempts in either. Both were backed up and the newest merged into the canonical folder.
- Status: VERIFIED (`git rev-parse`; `git check-ignore`). No model calls, installs or research actions.

## 2026-09-22 | Documentation | Overnight learning and research-documentation pack
- Authorship: Leo authorised the pack; Codex coordinated it overnight and relayed Leo's instructions; Claude wrote it and ran offline checks only. No model calls, installs, experiments or publishing.
- Tracked: `RESEARCH_ROADMAP.md` now has the pending-study notes (the two questions; supplied-function differentiation vs deriving dynamics from a Lagrangian; symbolic vs sample-point equivalence; the extra-turn confound) and recommendations R1–R5, *awaiting approval*. `HANDOFF.md` is updated.
- Clarification of earlier wording: "the system reproduced/reproduces the least-squares slope to within rounding" (V1 README; checkpoint 5 entry above) describes the **output values only**. The saved evidence doesn't establish the internal method. V1 shows that *offering* the tool gave no accuracy gain on these cases; the benefit of *executing* it is untested (0 executions). Earlier entries are left as written.
- Local (gitignored): `LEARNING_REVIEW.md` in the canonical folder. It has a START HERE route, the evidence-linked chronology, findings with uncertainty (12/12 descriptive, plus a qualified, illustrative binomial interval; see the correction below), the architecture and file map, questions consolidated to at most two per checkpoint (nothing deleted), and interview accounts. An earlier interview line that overclaimed the internal method was corrected.
- Status: OBSERVED (documentation). The offline commands in the workbook were re-run at 00:41.

## 2026-09-22 | Correction | Wording fixes from Codex's documentation verification
- Recorded 00:48 BST by Claude at the request Codex relayed. Four wording issues were fixed in place (documentation only, no code, runs or new questions):
  1. **Attribution in the interview scripts** (local workbook): the scripts now say Leo designed and directed the project, Claude implemented and tested the fixes, and Codex identified and reproduced the defects. Previously they said "I built" and "I fixed both".
  2. **Confidence bounds:** 0.735 and 0.265 are illustrative exact binomial (Clopper–Pearson) interval endpoints. They assume independent trials with a common success or discordance probability from a defined population. V1's small, fixed, synthetic, sign-balanced set with one run per case doesn't meet that, so they aren't general accuracy bounds or a measure of run-to-run variability. 0.265 is the endpoint of a two-sided 95% interval; the one-sided 95% upper bound is 0.221. The unconditional "≥ 0.735 at 95%" wording was removed from the entry above and from the workbook.
  3. **`RESEARCH_ROADMAP.md`:** the stale "Any accuracy estimate…" line was replaced with the actual limitation (no general accuracy estimate or cross-model ranking; the case-set accuracy is reported). The V0 remaining-work heading is marked completed and historical.
  4. **Derivation vs formulation:** starting from a supplied Lagrangian tests derivation. Choosing coordinates and assumptions and constructing the Lagrangian from a physical description tests formulation. These are separated in the roadmap (including R1) and workbook section D; they remain recommendations awaiting approval.
- Status: OBSERVED (documentation). Paragraphs re-read after editing.

## 2026-09-22 | Release | Repository made public after a pre-publication audit

- Decision (Leo, ~19:20 BST, session): "let's make the work public on github first of all. This is fine to be public." Two follow-up decisions were put to him after the audit and he chose both recommendations: publish with `LEARNING_REVIEW.md` left in history, and publish both branches.
- Pre-publication audit, run by Claude before any visibility change (read-only, all refs and all history):
  - Tracked at HEAD: 36 files on `main`, plus `LINEAGE.md` and `PROPOSAL.md` on the research branch. `git diff --stat v1.0.0 HEAD -- src tests data results` is empty, so the published code, data and results are exactly V1's.
  - Secret and identifier scan across every blob in `git rev-list --all`: no matches for `sk-ant`, `api_key`, `API_KEY`, `Bearer`, `session_id`, `uuid`, `@gmail`, the user name, or any absolute path (`/Users/`, `/home/`). No medical or personal-health terms. The words "employer", "interview" and "CareerOps" appear only as policy text in the instruction files and log ("No medical details, private messages, credentials or employer data belong in the public log"), not as data.
  - Tracked episode traces were checked field by field: they carry model ID, CLI version, token counts, prompt text and hashes, control flags and grades. No session identifiers, working directories or machine metadata. `raw_trace` holds a relative path to the gitignored `results/raw/`.
  - `git stash list` and `git fsck --lost-found` are both empty. Origin holds two branches and the two tags.
  - **Found and accepted:** `LEARNING_REVIEW.md` survives in history in three versions (16,596 / 17,728 / 20,227 bytes, commits `60fe171`, `d7e500a`, `ce07160`) from before it was untracked at `94499d0`. Its content is tutoring material only: catch-up tasks, ten exam questions, a marking scheme, worked solutions and an empty attempts table. Purging it would rewrite every commit after `60fe171`, including `8d336d8` (`v1.0.0`) and `f504c57` (`v0-protocol-freeze`), which would break the immutable-tag rule and invalidate the hashes cited in `LINEAGE.md`, `HANDOFF.md` and this log. Leo chose to publish as-is.
- Action: `gh repo edit retinapeg/agentic-physics-bench --visibility public --accept-visibility-change-consequences`, run by Claude at Leo's direction.
- Result: `gh repo view --json visibility` returns **`PUBLIC`** for `retinapeg/agentic-physics-bench` (default branch `main`). The superseded `retinapeg/agentic-physics-bench-analytic` was re-checked and remains **`PRIVATE`**.
- Known cosmetic consequences, not defects: `raw_trace` fields point at gitignored files, so those paths dangle for a public reader; `LINEAGE.md` and `HANDOFF.md` name the superseded private repository, which will 404 for readers; the inherited V1 section of `HANDOFF.md` still reads "Repo: private", correct as history and superseded by the current-state section.
- README re-read as a public reader: it leads with the result table but states in the same screen that both conditions sat at the ceiling, that the tool was never exercised, and that the pilot cannot measure a tool benefit. No wording change was needed.
- Anonymous check (unauthenticated `curl`, so it does not rely on the signed-in `gh` session): the repository page returns HTTP 200 and `raw.githubusercontent.com/.../main/README.md` returns HTTP 200; the superseded analytic repository returns HTTP 404, as expected while private.
- Status: VERIFIED (visibility confirmed by `gh` and by unauthenticated `curl` after the change; audit commands run in session). No model calls, installs or experiments.
- Lesson: TODO (Leo)

## 2026-09-23 | V1 verification | Release audited in an isolated checkout: complete, one environment limitation
- Authorship: Claude ran every check at Leo's direction (task brief of 2026-09-23); nothing in V1 was changed.
- Isolated checkout: `git worktree add --detach <scratch>/v1-verify v1.0.0` → `8d336d8`.
- A. Offline checks: `python3 -m unittest tests.test_ls_slope tests.test_tasks tests.test_evaluate tests.test_agent tests.test_controls tests.test_analyze` → `Ran 36 tests … OK`.
- B. Recount from `results/episodes_scored.jsonl`: 24 records, 24 unique (case, condition) and episode IDs, execution order equal to `data/scored_plan.json`; schema 3 throughout; 24 valid, 0 control violations (per record and per turn); 24 model calls (= turn count), 0 tool requests, 0 tool executions; 12/12 correct in each condition; regrading every saved `response_text` against `scored_keys.jsonl` with `evaluate.grade` reproduces every saved grade and error; every answer equals `a_ref` rounded to 1–6 decimals (21 at 3 dp, 2 at 4 dp, 1 at 1 dp); no prompt contains any key value to 4 dp; init metadata identical in all 24 calls (`claude-opus-5`, `tools: []`, `mcp_servers: []`, CLI 2.1.278); 48 assistant messages all `claude-opus-5`; no stderr; all rate-limit statuses `allowed`, no overage.
- C. `python3 src/tasks.py && python3 src/tasks.py scored`, `python3 src/analyze.py && python3 src/chart.py` → `git status --short data/ results/` empty (byte-identical).
- D. All 14 manifest hashes match. `verify_freeze` fails only on the CLI version: installed **2.1.280** vs frozen 2.1.278. That is a present-day environment limitation, not a defect: no V1 code, data or result depends on it, and no historical episode was rerun. Frozen files are unchanged between `v0-protocol-freeze` and `v1.0.0` (only `analyze.py` and `chart.py`, outside the manifest, were added).
- F. The workflow prompt (`prompts/workflow_turn1.txt`) offers `fit_line` explicitly with the exact request JSON, so the model was offered the custom tool in every workflow episode. The raw traces show one redacted thinking block per call (signature only, ~476 thinking tokens on s-07), so the model's reasoning about the tool is unrecoverable: the explanation of zero uptake remains open.
- G. The tool-dispatch branch, driven end to end through `run.run_episode` with scripted CLI replies (request → `fit_line` → final): valid, 2 calls, 1 execution, the tool result and the previous reply appear verbatim in the saved turn-2 prompt, and the relayed slope grades correct with zero error.
- Live smoke check (1 call, V1 argv, CLI 2.1.280, empty temp dir, raw output kept outside the repo): `model claude-opus-5`, `tools: []`, `mcp_servers: []`, no stderr, `apiKeySource none`, overage rejected; usage windows five-hour 3 %, seven-day 20 %. Safe-mode init now lists 3 plugins (V1: 1); whether any reach the model's context is still unverified (V1's caveat carries over). Elapsed 28.9 s for a one-word reply (V1 calls took 6–9 s).
- Added after the V2 advisor discovery (13:10): the 24 V1 scored raw traces were scanned for server-side tool blocks as well as `modelUsage`: assistant content blocks are `thinking` (24) and `text` (24) only, `modelUsage` lists `claude-opus-5` only (24/24) and every usage iteration is of type `message`. V1 is unaffected on both signals.
- Verdict: **V1 is complete.** Offline evidence reproduced; the historical live execution is supported by the saved records; the only limitation is the newer CLI. The observation stands as written: on the 12 held-out tasks the tool-enabled system returned correct answers without requesting the optional tool, and both conditions reached the ceiling. Why is not established.
- Status: VERIFIED (commands and outputs above, run in session).

## 2026-09-23 | V2 design | Difficulty × tool policy: three groups, three conditions, fixed tolerance
- Authorship: Leo set the question, the three-condition design and the bounds (task brief); Claude designed the groups, simulated the tolerance justification and wrote the code, tests and protocol draft (`EXPERIMENT_V2.md`, awaiting approval).
- Groups (one family, V1's): easy = V1's generator with a new seed (10 points, uniform grid, σ 0.5); moderate = 24 points, t = 0.5·i + U(0, 0.4) s, σ 1.0; hard = 40 points, the same irregular grid, σ 2.0. Velocities shown to 2 dp everywhere; |a_true| in (0, 5], sign-balanced; reference = least-squares slope of the displayed strings.
- Tolerance kept at ±0.01 m/s² in every group. Simulation with the shipped generator `tasks_v2.make_case_v2` (4,000 draws per group, seed 7; an earlier draft with a symmetric ±0.25 jitter gave slightly different figures and was replaced on 2026-09-23 at 13:15): pass rates under ±0.01 for the endpoint slope 7.3 / 6.9 / 5.7 %, split-halves 12.4 / 22.6 / 26.0 %, 10-point subsample 100 / 13.3 / 8.4 %, times rounded to the 0.5 s grid — / 43.2 / 66.2 %, velocities rounded to 1 dp 88.8 / 100 / 100 %; the exact slope rounded to 2 dp passes 100 %. Extra displayed decimals do not matter at this tolerance, so the levers are N, grid irregularity and noise, not precision. A first jitter draft (U(−0.2, 0.2)) produced a negative first time (−0.01 s) on a development task and was replaced by U(0, 0.4) before any model call; the test now asserts t ≥ 0 and strictly increasing.
- Conditions: `no_tool`, `optional_tool`, `required_tool`; two fresh calls in every condition, ≤ 1 execution, final answer = turn 2; noncompliance in the required condition is recorded and continues to turn 2. Matrix 18 × 3 × 3 = 162 episodes, 324 calls; development 6 × 3 × 1 = 18 episodes, 36 calls; seeded block plan.
- Implementation, all new files (V1's frozen files untouched; `git diff v1.0.0 -- src/tasks.py src/tools.py src/evaluate.py src/models.py src/agent.py src/run.py prompts/*.txt data/*.jsonl data/*.json` empty): `src/tasks_v2.py`, `src/agent_v2.py`, `src/run_v2.py`, `src/analyze_v2.py`, `src/chart_v2.py`, `prompts/v2/`, `data/v2/`, `tests/test_v2_*.py` (37 checks) → with V1's 36, `Ran 73 tests … OK`. CI: `.github/workflows/checks.yml` runs the same checks and the regeneration comparisons.
- Second system: Codex/GPT deferred (no tool-removal option in `codex exec`; live web search enabled in the local config; served model not exposed). Recorded, not blocking.
- Status: OBSERVED (design and offline verification). The development gate (`EXPERIMENT_V2.md` section 9) was declared before the development batch started.

## 2026-09-23 | V2 development gate, stage 1 | Harness works live; no-tool at ceiling in every group; optional requests rise with difficulty
- Authorship: Claude ran the pre-declared development batch (`python3 src/run_v2.py dev`, 11:58–12:24 BST, 18 episodes, 36 calls, CLI 2.1.280, `claude-opus-5`, effort high) at Leo's direction. Codex's review fixes (previous entry's follow-up below) landed while it ran; the batch used the pre-fix runner, so it has no attempt markers.
- Observed (`results/v2/dev_stage1/summary_dev.md`, archived with the episodes, tasks, keys and plan it used):
  - **G-a passed:** 18/18 episodes valid, exactly 2 calls each, 0 control violations, 0 timeouts. In `required_tool` 6/6 requests were valid, executed and relayed with |final − slope| = 0 (compliance 6/6).
  - **G-b:** `no_tool` correct on 2/2 easy, 2/2 moderate and 2/2 hard (40 points). Per-call median thinking tokens rose 742 → 2,316 → 4,532 (easy → moderate → hard) and wall time 27 → 63 → 108 s per call. The escalation clause therefore fired: hard group raised from 40 to 60 points.
  - **Optional tool requested:** easy 0/2, moderate 1/2 (d2-01), hard 2/2. Every executed result was relayed exactly. This is the first optional request in the project (V1: 0/12).
  - **G-c:** one turn-1 reply (d3-02, `no_tool`) was a fenced JSON block (` ```json … ``` `), recorded as `malformed_json` by the strict parser; the episode's turn-2 answer was correct. The one permitted wording revision adds "(no code fences, no other text)" to all four prompt templates.
  - Correctness overall 18/18; every turn-1 final answer was also correct (11/11).
- Stage 2: the six hard episodes rerun on the 60-point tasks with the revised wording (12 calls); easy and moderate records carried over unchanged into `results/v2/episodes_dev.jsonl` because their tasks did not change. Freeze follows stage 2 regardless of outcome.
- Codex review of the V2 code (read-only, `gpt-6-astra` requested via `codex exec --sandbox read-only --ephemeral --ignore-user-config`; `gpt-6-sol`, the config default, is rejected on the ChatGPT account) found three executable defects, all reproduced and fixed by Claude with regression tests before any freeze: (1) an episode interrupted after its first call left no record, so resume replayed it and its first call escaped the cap → attempt markers written before the first call (`results/v2/attempts_*.jsonl`), interrupted attempts stay in the denominator as `interrupted`; (2) the timeout branch replaced every control check with an empty list, hiding positively observed native tool use or overage in a partial trace → only missing evidence and the synthetic timeout stderr are exempt; (3) a JSON integer such as 10**400 raised `OverflowError` in the inherited parser → recorded as `bad_acceleration` (V1's frozen parser keeps the latent bug; no V1 output triggered it). 77 offline checks pass.
- Status: OBSERVED (development, not scored). No scored inference.

## 2026-09-23 | Control failure found | A server-side advisor consulted a second model inside "no-tool" calls; stages 1–2 void
- Found by: the multi-agent Claude review (59 agents, 5 dimensions, 2 refuters per finding; 14 findings confirmed, 13 refuted) reading one gitignored raw trace. Confirmed by Claude across all 48 stage-1/2 traces: 31 calls contain `server_tool_use` name `advisor` and `advisor_tool_result` blocks, an `advisor_message` iteration for `claude-fable-5-1`, and `modelUsage` listing both `claude-opus-5` and `claude-fable-5-1` (e.g. d1-02 optional turn 1: opus 1,040 output tokens; fable 7,237 in / 1,976 out). Stage 1: 24/36 calls, 16/18 episodes; stage 2: 25/36 calls, 16/18 episodes (`results/v2/dev_stage{1,2}/advisor_audit.json`).
- Why V1's controls missed it: `run.control_violations` counts native `tool_use` blocks and checks `message.model` of assistant events; the advisor is a *server-side* tool (`server_tool_use`) and the second model appears only in `usage.iterations` and `modelUsage`. Under `--tools ""` and `--safe-mode` the tool still ran. V1's 24 scored traces and today's smoke call show only `claude-opus-5`, so V1 is unaffected.
- Switch: the CLI binary reads `CLAUDE_CODE_DISABLE_ADVISOR_TOOL` (and `CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL`); no flag or settings key is documented in `--help`. Probe (1 call, d2-01 `no_tool` turn-1 prompt, variable set): content blocks `thinking, text`; `modelUsage` = `claude-opus-5` only; no iterations. The reply, however, was a fenced bash script that computes the slope in Python, not a number: without the advisor the model reached for code it cannot run (8.6 s, no arithmetic). This is the first sign that the clean system may behave differently from what stages 1–2 showed.
- Consequences applied: (1) `src/run_v2.py` sets `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` for every call, records it per episode and in the manifest, and `verify_freeze` checks it; (2) new per-call violations `server_tool_use:<name>`, `unexpected_model_usage:<models>`, `unexpected_iteration:<types>` (regression tests in `tests/test_v2_run.py`); (3) stages 1 and 2 archived verbatim with audits and READMEs and declared void for the gate; the escalation to 60 points reverted (hard = 40; data regenerated, identical to stage 1's); the wording revision kept; (4) stage 3 = the full development plan rerun on a fresh file with the controls enforced (`python3 src/run_v2.py dev-restage stage2`, then `dev`).
- Other confirmed review findings fixed in the same pass (each with a test): a turn-2 control violation lost the loop's turn-1/tool state (the loop now fills a caller-owned state dict); `RecursionError`/`ValueError` from the parser on pathological JSON now record `malformed_json`; a lone surrogate in an echoed reply no longer crashes the subprocess encoding; `stderr_first_line` is redacted of user directories; the tool-failure taxonomy gained `executed_then_wrong_units` so its rows partition executed episodes; a turn-1 no-reply in `required_tool` is compliance-undefined (`None`), not noncompliance; per-episode rows read `tool_executions`; the chart's accessible description matches what is drawn; `analyze_v2.py` and `chart_v2.py` joined the freeze manifest; `dev-restage` documents the development re-run mechanism the gate needed; the offset justification in `EXPERIMENT_V2.md` was corrected. 90 offline checks pass.
- Lesson (Claude's reading; Leo's own wording TODO): "no tools" must be verified against everything the trace reports, not only the tool list the CLI prints; a control that passed in one CLI version can be blind to a feature added in the next.
- Status: VERIFIED (trace audit, probe, tests). Stage-3 outcome in the next entry.

## 2026-09-23 | V2 development gate, stage 3 (clean) | No-tool fails with difficulty; the optional tool is requested every time
- Authorship: Claude ran `python3 src/run_v2.py dev` (12:48–12:56 BST; 18 episodes, 36 calls; CLI 2.1.280, `claude-opus-5`, effort high, `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1`, amended controls enforced per call) at Leo's direction, on a fresh `results/v2/episodes_dev.jsonl` after `dev-restage stage2`.
- Controls: 36/36 calls report `modelUsage` = `claude-opus-5` only, no server-side tool blocks, no non-message iterations, no stderr, no violations. 18/18 valid, exactly 2 calls each, 0 timeouts.
- **G-b, difficulty (`no_tool`):** easy 2/2, moderate 1/2, hard 0/2 correct. Every moderate and hard turn-1 reply (4/4) was an attempt to run code that the system does not have (a fenced bash block, `<invoke name="Bash">` syntax, a "googletool" command object): `malformed_json` under the strict rule, classified `attempted_code_execution` by the analysis heuristic. The turn-2 answers were then −1.2959 vs −1.3095 (d2-01, |error| 0.0135), 3.4839 (d2-02, correct after 1,900 thinking tokens), −3.0156 vs −3.0652 (d3-01, 0.0496) and 2.4813 vs 2.5903 (d3-02, 0.1089). Median thinking tokens per call: easy 666, moderate 32, hard 13; median 9–10 s per call. The escalation clause did not fire; the hard group stays at 40 points.
- **Tool conditions:** `optional_tool` requested `fit_line` in 6/6 episodes at turn 1 (0 thinking tokens, 3.6–4.7 s), executed 6/6, final answers equal to the tool slope (relay |Δ| = 0) 6/6. `required_tool` compliant 6/6, correct 6/6. Task-level paired difference tool − no tool: +0.50 (3 tasks favour the tool, 3 tied; cluster-bootstrap 95 % interval [+0.17, +0.83] over 6 development tasks, which is a description, not a result).
- **G-a passed; G-c:** the malformed replies are code attempts, not fence-wrapped JSON; the one permitted wording revision was used in stage 1 and is kept. No further prompt change. Sanitisation: one reply quoted the CLI's per-session scratchpad path; the runner now redacts user, temp and session directories from every text field at write time (`run_v2.redact`, `<path>`), and the stage-3 file was passed through the same function once (1 record changed; raw traces untouched).
- **Comparison caveat:** stage 3 requested the optional tool 2/2 on easy tasks where V1 requested it 0/12 and stages 1–2 0/2. Between V1 and stage 3 the CLI version (2.1.278 → 2.1.280), the turn structure (one call → two), the prompt wording ("no code fences, no other text") and the advisor state all changed; between stages 1–2 and stage 3 the wording (for easy tasks) and the advisor state changed. The difference is observed, not attributed.
- Gate decision: **freeze-ready.** Scored inference waits for Leo's approval of `EXPERIMENT_V2.md` section 11 (decisions V2-1 to V2-8), then `python3 src/run_v2.py freeze <run_id>` and `scored-batch`.
- Evidence: `results/v2/episodes_dev.jsonl`, `results/v2/summary_dev.{json,md}`, `results/v2/chart_dev.svg`; 90 offline checks OK.
- Status: OBSERVED (development, not scored).

## Topics to capture as they occur

Model vs agent vs pretrained weights; API/SDK vs model identity; benchmarks vs evals; reference validation; data leakage; prompts and configuration hashes; structured-output failures; tool dispatch and stopping; retries and missing denominators; retrieval vs generation errors; unsupported claims vs numerical mistakes; RAG vs fine-tuning; paired analysis; reproducibility; what I implemented vs delegated.
