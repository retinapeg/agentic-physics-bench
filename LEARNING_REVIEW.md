# Learning review: Leo's revision workbook

For Leo to work through later, at his own pace, after or between build sessions. It is not used during build sessions unless Leo asks. It holds:
- **Catch-up tasks:** work an assistant did during the build, or that Leo skipped, which he should be able to do himself.
- **Exam-style questions:** about what the project actually built or decided. They start from physics or numerical reasoning, then connect it to AI engineering.
- **Walkthroughs:** guided exercises, with worked solutions kept separate.

How to use it: pick one item, answer it on paper or in your notes, then check the Marking scheme or the task's check. Record the result in the Record of attempts. Attempt a walkthrough before opening its worked solution.

Authorship: drafted and maintained by Claude at Leo's request, starting 2026-09-21. Leo reviews and may edit. The file's purpose (a workbook for later review and catch-up) was set by Leo on 2026-09-21. The marking-scheme numbers were checked with python3 against `EXPERIMENT.md` section 3.

## Catch-up tasks

| ID | From | What happened during the build | Your task | Check |
|---|---|---|---|---|
| C1 | 0 | Claude wrote the checkpoint 0 log entry from the traces | Write the checkpoint 0 "Lesson" in `RESEARCH_LOG.md` in your own words | The entry no longer says TODO |
| C2 | 0 | Leo ran the Claude smoke test, Codex ran the GPT smoke test, Claude summarised both traces | Open `results/checkpoint0-claude.jsonl` and `results/checkpoint0-codex.jsonl` (local only). In each, find the model field, tool list, reported input tokens and overage status, or note that it's missing | Your findings match the checkpoint 0 entry in `RESEARCH_LOG.md` |
| C3 | 1a | The chat explanation of `a_ref` vs `a_true` was assistant-drafted | Write the 1a "Lesson" in `RESEARCH_LOG.md` in your own words | The entry no longer says TODO; see also Q2 |
| C4 | 1a | Codex supplied Sxx = 20.625 s² and Claude rechecked it | Compute Sxx for t = 0, 0.5, …, 4.5 s by hand | Q3(a) in the Marking scheme |
| C5 | 1a | Claude drafted the `EXPERIMENT.md` skeleton | Without looking, list everything that must be frozen before scored runs, then compare with `EXPERIMENT.md` section 10 and the open decisions in `HANDOFF.md` | You named seeds, generator, prompts, reference, tolerance, episode limits and scoring rule |
| C6 | 1b | Claude tested `tests/test_ls_slope.py` against deliberately wrong versions in a scratch folder | Write the endpoint-slope version of `ls_slope` in a scratch file and run the tests against it | 2 failures, as recorded in `HANDOFF.md` row 14; see also Q10 |
| C7 | 1b | Claude wrote `tests/test_ls_slope.py` | Add one test of your own, e.g. a positive slope with unsorted times. Show that it fails on a wrong version | `python3 -m unittest -v tests.test_ls_slope` passes on your code and fails on the wrong version |
| C8 | 1b | Only if you read the W1 worked solution before writing `ls_slope` | Rewrite `ls_slope` from the formula without looking | The tests pass |

## Questions

### Q1 · Checkpoint 0 · Ready when: now · [8 marks]
(a) [3] You record a signal through a digital oscilloscope that applies its own undocumented filtering before display. What must you record so that a colleague can (i) reproduce the measurement and (ii) attribute it correctly? What can't you claim about the raw signal?

(b) [5] The Claude smoke trace reports `model: claude-opus-5`, `tools: []` and about 4,605 reported input tokens for a one-word answer. The Codex trace reports 16,297 input tokens and has no served-model field. For each system, state one thing its trace establishes and one thing it doesn't. Name two fields your adapter must record that neither smoke trace contains.

### Q2 · Checkpoint 1a · Ready when: now · [6 marks]
(a) [2] A student estimates g from a least-squares fit to their own drop-timing data and reports 9.74 ± 0.05 m/s². The marker grades against 9.81 m/s². What is the marker actually testing, and when is that unfair?

(b) [4] In your own words: why is our answer key `a_ref` (the least-squares slope of the displayed table) rather than `a_true`? Define leakage for this benchmark and give one concrete leakage path that exists in our setup if we are careless.

### Q3 · Checkpoint 1a · Ready when: now · [8 marks]
(a) [5] For v_i = v0 + a·t_i + ε_i with independent ε_i ~ N(0, σ²), show that the least-squares slope has Var(â) = σ² / Σ(t_i − t̄)². Compute Σ(t_i − t̄)² yourself for t = 0, 0.5, …, 4.5 s; Codex supplied 20.625 s², so confirm or refute it independently. Give SD(â) at σ = 0.5 m/s.

(b) [3] The grader compares answers with `a_ref`, not `a_true`. Does SD(â) set the grading tolerance? If not, what is it evidence about?

### Q4 · Checkpoint 1a · Ready when: now · [8 marks]
(a) [5] The endpoint estimator is â_end = (v_last − v_first)/(t_last − t_first). On our grid, give SD(â_end) and SD(â_end − â_LS) as multiples of σ.

(b) [3] Suppose the tolerance is much larger than SD(â_end − â_LS). What happens to the scores of both conditions, and what does the pilot then fail to measure? Name the concept.

### Q5 · Checkpoint 1a · Ready when: now · [7 marks]
(a) [4] With σ = 0.5 m/s on our grid and a_true = −0.1 m/s², what is the probability that `a_ref` > 0? Show the z-value.

(b) [3] Our split is sign-balanced on `a_true`. Give two remedies for sign flips and one side effect of each. Why must the chosen rule be in `EXPERIMENT.md` before the scored cases are generated?

### Q6 · Checkpoint 1a/1b · Ready when: now · [6 marks]
(a) [3] Read "Notes on Reproducibility" in the Python `random` documentation. Besides the seed, what determines the numbers our generator will emit?

(b) [3] What must the freeze record contain so that a reviewer can check the scored cases were not regenerated after results were seen?

### Q7 · Checkpoint 1a · Ready when: now · [6 marks]
(a) [2] In a blinded analysis, compare hiding the signal region from the analyst with checking afterwards whether the analyst looked. Which is the stronger control, and why?

(b) [4] Claude ran with `--tools ""` and its trace shows `tools: []`. Codex ran in a read-only sandbox. Classify each as prevention, detection or neither. If the direct condition had a shell available, what would it actually measure?

### Q8 · Checkpoint 1b · Ready when: `ls_slope` passes its checkpoint check · [5 marks]
(a) [3] Why is a perfect straight line, such as v = 3 − 2.5t, a weak test of `ls_slope`? Give one wrong implementation that passes it but fails on t = [0, 0.5, 1.0, 1.5] s, v = [5, 2, 3, 1] m/s.

(b) [2] What general property should a test case for a reference or grading function have?

### Q9 · Checkpoint 1b · Ready when: the dev-01 check has been run · [6 marks]
(a) [3] `ls_slope` and `statistics.linear_regression` run on the same parsed numbers. Name a bug they would share, so that they agree to 1e-12 and are both wrong.

(b) [3] What makes a hand calculation from the printed table independent where the stdlib check is not? How does this carry over to validating an eval's answer key?

### Q10 · Checkpoint 1b · Ready when: `ls_slope` passes `tests/test_ls_slope.py` · [5 marks]
(a) [2] Before trusting a new thermometer, you might check it in ice water and in boiling water. Why is checking it only at room temperature not enough?

(b) [3] Before your code existed, the checks in `tests/test_ls_slope.py` were run against one correct and two deliberately wrong versions of `ls_slope`: an endpoint slope, and a `sum/len` mean. Why test the tests? What did each wrong version reveal about which checks matter?

## Walkthroughs

### W1: from the least-squares formula to `ls_slope` [GUIDANCE]

Status: guidance only, until Leo's own `src/tasks.py` exists and both checks pass. After that, the Record of attempts shows how it went.
Authorship: Leo specified the five-step outline. Claude drafted the explanations, hints and worked solution, and tested the worked solution in a scratch directory outside the repo (2026-09-21, 18:20 BST). The implementation in `src/tasks.py` is Leo's to write.

#### The idea in physics terms
The best-fit line passes through the centroid (t̄, v̄). Measure every point from the centroid. The slope is then how t and v vary together, divided by how t varies alone:

â = Sxy / Sxx, with Sxx = Σ(tᵢ − t̄)² and Sxy = Σ(tᵢ − t̄)(vᵢ − v̄).

Units: (s · m/s) / s² = m/s².

#### Exercise
Write `ls_slope(t, v)` in `src/tasks.py` in five steps:
1. Validate. Raise `ValueError` if the lengths differ, if there are fewer than two points, or if any value is not finite.
2. Calculate the means t̄ and v̄.
3. Calculate Sxx. If it is zero (all times equal, so no slope exists), raise `ValueError`.
4. Calculate Sxy from corresponding (tᵢ, vᵢ) pairs.
5. Return `Sxy / Sxx` as a `float`.

Known example: t = [0, 0.5, 1.0, 1.5] s, v = [5, 2, 3, 1] m/s gives â = −2.2 m/s².

#### Python pieces
- **`math.isfinite(x)`** is `True` for ordinary numbers and `False` for `nan`, `inf` and `-inf`. A `nan` spreads silently through arithmetic, and every comparison with it is `False`. So a bad value would give a `nan` slope and quietly fail a grade. Checking at the start turns a silent problem into a loud error.
- **`statistics.mean(xs)`** is the arithmetic mean. It raises an error on empty input. For floats it rounds only once, at the end, so the mean of identical values is exactly that value. `sum(xs) / len(xs)` doesn't guarantee this: for `[0.1, 0.1, 0.1]` it gives `0.10000000000000002`.
- **`zip(t, v)`** pairs items by position: `list(zip([1, 2, 3], ["a", "b"]))` gives `[(1, 'a'), (2, 'b')]`. It stops at the shorter input without warning. That's why step 1 checks the lengths first. `zip(t, v, strict=True)` also works in Python 3.10+.
- **`sum((ti - t_bar) ** 2 for ti in t)`** is a generator expression and reads like Σ. `for ti in t` runs over the times, `(ti - t_bar) ** 2` is the term (`**` is "to the power"), and `sum(...)` adds the terms. It is Sxx written almost exactly as the maths.

#### Hints (smallest first)
1. Put all validation first, one `if …: raise ValueError("…")` per rule.
2. Check finiteness with a loop over the values of both lists, or with `all(...)`.
3. `Sxx == 0` is a safe exact test only if the mean of identical times is exact. With `sum/len`, three times of 0.1 s give Sxx ≈ 5.8 × 10⁻³⁴ instead of 0, and the "slope" becomes enormous. `statistics.mean` avoids this.
4. For Sxy, loop over `zip(t, v)` so each tᵢ meets its own vᵢ.

## Record of attempts

| Date | Item (Q or C) | Marks / done | Hints used | Unaided / assisted | Note |
|---|---|---|---|---|---|

## Marking scheme (check after answering)

**Q1 (8)**
- (a) 1: instrument model, firmware version and settings. 1: acquisition parameters, and the processing chain or calibration as far as it is known. 1: claims attach to "the signal as seen through this instrument"; filtered-out features of the raw signal can't be claimed.
- (b) 1: Claude trace establishes the provider-reported model ID and that no tools were available in that run. 1: it doesn't establish what the ~4,605 reported input tokens consist of, or how the bare model behaves without the wrapper. 1: Codex trace establishes a response with no tool events. 1: it doesn't establish the served model, only that `gpt-6-astra` was requested. 1: two valid fields, e.g. exact prompt text and the full command line. Also accept: CLI version, config/settings, working directory, prompt hash.

**Q2 (6)**
- (a) 1: the marker tests recall of the accepted constant, not the analysis of the student's data. 1: unfair when the data legitimately give a different best fit, so a correct analysis is penalised.
- (b) 2: the key must be a deterministic function of exactly what the model sees. `a_ref` answers the task actually posed. `a_true` differs by noise and rounding (SD ≈ 0.11 m/s² at σ = 0.5), so grading against it marks correct fits wrong and rewards luck. 1: leakage means information outside the task input reaching the solver or shaping the benchmark. 1: a concrete path, e.g. keys, `data/` or generator code readable from the CLI's working directory; project instruction files loaded into context; scored cases used to tune prompts.

**Q3 (8)**
- (a) 1: â = Σ c_i v_i with c_i = (t_i − t̄)/Sxx. 1: Σc_i = 0 and Σc_i t_i = 1, so â is unbiased. 1: Var(â) = σ² Σc_i² = σ²/Sxx. 1: Sxx = 0.25 × Σ_{k=0..9}(k − 4.5)² = 0.25 × 82.5 = 20.625 s². 1: SD = 0.5/√20.625 ≈ 0.110 m/s².
- (b) 2: no. The key is fixed for a given table, so tolerance is set by the required answer precision and reporting/rounding of the answer. 1: SD(â) describes how far `a_ref` sits from `a_true` across noise draws. It bears on difficulty and on whether shortcuts land within tolerance, not on grading error.

**Q4 (8)**
- (a) 2: Var(â_end) = 2σ²/(4.5 s)², so SD ≈ 0.314σ. 3: â_LS is the best linear unbiased estimator, so Cov(â_LS, â_end − â_LS) = 0 and Var(â_end − â_LS) = σ²(2/20.25 − 1/20.625). SD ≈ 0.224σ, i.e. ≈ 0.112 m/s² at σ = 0.5. Accept a direct calculation via the estimator weights.
- (b) 1: both conditions saturate; a shortcut or mental estimate scores as well as a real fit. 1: the pilot can't detect a tool effect. 1: concept: construct validity, discriminative power or ceiling effect.

**Q5 (7)**
- (a) 1: SD(a_ref) = 0.5/√20.625 ≈ 0.110 m/s². 1: z = 0.1/0.110 ≈ 0.91. 2: P = Φ(−0.91) ≈ 0.18. Checked: 0.182 analytic, 0.183 Monte Carlo with 200,000 draws.
- (b) 1: two remedies. Options: a floor |a_true| ≥ a_min (at a_min = 0.5 the flip probability ≈ 3 × 10⁻⁶); reject-and-redraw when signs differ; balance on the sign of `a_ref`. 1: a side effect for each, e.g. the floor changes the tested distribution and excludes near-zero cases; redraw conditions the data on the noise and must be deterministic and logged. 1: choosing the rule after seeing scored cases is selection on the test set.

**Q6 (6)**
- (a) 1 each, max 3: RNG library and algorithm (`random` vs NumPy); Python version (the docs promise that only `random()` reproduces for the same seed, not other methods); number and order of draws (per sign, per case, per point); parameter values; the generator code itself.
- (b) 1: commit hash of the generator code. 1: SHA-256 of the emitted case and key files, committed before any scored run. 1: seed and Python version recorded, with that commit earlier than the first scored trace.

**Q7 (6)**
- (a) 1: hiding (prevention) is stronger. 1: checking afterwards depends on complete logs and can't undo exposure.
- (b) 1: Claude is prevention, verified by trace metadata. 1: Codex's read-only sandbox is neither; it restricts writes, not command execution. At best it allows detection via zero tool events in the JSONL. 1: with a shell, "direct" becomes model plus calculator, so the direct/workflow contrast collapses. 1: the shell could also read files in the working directory, which is leakage.

**Q8 (5)**
- (a) 2: on a perfect line, many wrong estimators give the right slope, e.g. endpoint difference, mean of successive differences, any two-point slope. 1: on the given data the endpoint slope is −2.667 m/s² but least squares gives −2.2 m/s².
- (b) 2: a test must separate the correct implementation from plausible wrong ones. Use a known exact answer, noise, a negative sign and a nonzero intercept.

**Q9 (6)**
- (a) 1 each, max 2: fitting unrounded floats instead of the display strings; passing (v, t) swapped to both; the wrong case or column; the wrong time unit. 1: agreement checks the arithmetic, not the inputs.
- (b) 1: the hand check starts from the printed table, the artifact the model sees, by a different route. 1: independence means not sharing inputs or assumptions, not merely different code. 1: validate an eval key by an independent route from the displayed task, e.g. a second calculation that reads only the prompt file.

**Q10 (5)**
- (a) 1: a check must be able to fail, so test at points where a faulty instrument would disagree. 1: one point can't distinguish offset from gain errors, or a stuck reading from a working one.
- (b) 1: a check that passes on wrong code gives false confidence, so each check must fail on at least one plausible bug. 1: the endpoint version failed only the known-example and stdlib-comparison checks; on a perfect line it would have passed. 1: the `sum/len` version failed only the equal-times case with an inexact mean, showing that the zero-spread guard depends on how the mean is computed.

## Worked solutions [read after attempting]

<details>
<summary>W1: <code>ls_slope</code> worked solution and hand calculation</summary>

```python
import math
import statistics


def ls_slope(t, v):
    """Least-squares slope of v against t (units of v per unit of t)."""
    if len(t) != len(v):
        raise ValueError(f"t and v have different lengths: {len(t)} != {len(v)}")
    if len(t) < 2:
        raise ValueError("need at least two points")
    for x in list(t) + list(v):
        if not math.isfinite(x):
            raise ValueError("all values must be finite")

    t_bar = statistics.mean(t)
    v_bar = statistics.mean(v)

    s_xx = sum((ti - t_bar) ** 2 for ti in t)
    if s_xx == 0:
        raise ValueError("all times are equal; slope is undefined")

    s_xy = sum((ti - t_bar) * (vi - v_bar) for ti, vi in zip(t, v))
    return float(s_xy / s_xx)
```

Hand calculation for the known example (t̄ = 0.75 s, v̄ = 2.75 m/s):

| i | t (s) | v (m/s) | t − t̄ | v − v̄ | (t − t̄)² | (t − t̄)(v − v̄) |
|---|---|---|---|---|---|---|
| 0 | 0 | 5 | −0.75 | 2.25 | 0.5625 | −1.6875 |
| 1 | 0.5 | 2 | −0.25 | −0.75 | 0.0625 | 0.1875 |
| 2 | 1.0 | 3 | 0.25 | 0.25 | 0.0625 | 0.0625 |
| 3 | 1.5 | 1 | 0.75 | −1.75 | 0.5625 | −1.3125 |
| Σ | | | 0 | 0 | 1.25 | −2.75 |

â = −2.75 / 1.25 = −2.2 m/s². The intercept is v̄ − â·t̄ = 4.4 m/s. For comparison, the slope between the first and last points is −2.667 m/s².

Scratch-directory output of the worked solution (not Leo's code): `-2.2`, and `ValueError` for equal times, a `nan`, mismatched lengths and a single point.
</details>

## Notes for an AI tutor or maintainer

Maintaining this file during the build:
1. When an assistant does work Leo would otherwise have done (a calculation, a draft, a test, a command), add a catch-up task that says who did it.
2. After each checkpoint, add at most two questions about what was actually built, each with a Marking scheme entry and its drafter named. Don't write questions about components that don't exist yet.
3. Don't ask these questions during build sessions unless Leo asks.
4. If the protocol changes (grid, σ, tolerance), recheck the affected Marking scheme numbers.

Running a revision session:
5. Offer only items whose "Ready when" condition is met; check against the repo. Ask one question at a time, part (a) first, and wait for the answer.
6. Before Leo answers, don't reveal or paraphrase the Marking scheme or ask leading questions. If he asks for a hint, give the smallest useful one and record it.
7. Mark against the scheme, giving marks per point and naming any missed point in one line. Give the model answer only after marking, and only if Leo asks.
8. Record every attempt in the Record of attempts. Never record an assistant-drafted answer as Leo's own.
9. Walkthroughs are guidance, not evidence. Don't point Leo to Worked solutions before he attempts the exercise; if he reads it first, record "worked solution consulted".

**W1 code review checklist (tutor; used when inspecting Leo's `ls_slope`)**
- Validation happens before any arithmetic. Each of the four failures raises `ValueError` with a message that names the rule.
- Finiteness is checked for both t and v.
- Means come from `statistics.mean`, or the tutor asks why not (see Walkthroughs, W1 hint 3).
- Sxx is checked for zero before dividing. Sxy uses paired values.
- It returns a plain `float`. No rounding, printing or modification of the inputs.
- `python3 -m unittest -v tests.test_ls_slope` passes. Record the actual output in HANDOFF.md.
