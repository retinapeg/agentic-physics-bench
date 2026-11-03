#!/usr/bin/env python3
"""Build the historical evidence PDF from its immutable-input audit inventory.

No model calls, downloads, historical writes or inferred missing observations.
Requires reportlab==4.4.9 and pypdf==6.10.0 for the audited build.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape
from urllib.parse import quote

from reportlab import Version as REPORTLAB_VERSION
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    KeepTogether, HRFlowable,
)
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/evidence/2026-11-03/historical_inventory.json"
REPORT_DIR = ROOT / "reports"
PDF_NAME = "historical-evidence-2026-11-03.pdf"
INK = colors.HexColor("#142B3B")
TEAL = colors.HexColor("#087F8C")
LIGHT = colors.HexColor("#EDF4F6")
GRAY = colors.HexColor("#536570")
PAGE_W, PAGE_H = A4
STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle(name="CoverTitle", fontName="Helvetica-Bold", fontSize=29, leading=34, textColor=INK, spaceAfter=16))
STYLES.add(ParagraphStyle(name="Deck", fontName="Helvetica", fontSize=13, leading=18, textColor=GRAY, spaceAfter=16))
STYLES.add(ParagraphStyle(name="SectionTitle", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=INK, spaceAfter=16))
STYLES.add(ParagraphStyle(name="SubTitle", fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=TEAL, spaceBefore=11, spaceAfter=5))
STYLES.add(ParagraphStyle(name="Copy", fontName="Helvetica", fontSize=9.5, leading=14, textColor=INK, spaceAfter=8))
STYLES.add(ParagraphStyle(name="SmallCopy", fontName="Helvetica", fontSize=8, leading=11, textColor=GRAY, spaceAfter=6))
STYLES.add(ParagraphStyle(name="Cell", fontName="Helvetica", fontSize=8.2, leading=11, textColor=INK))
STYLES.add(ParagraphStyle(name="HeaderCell", fontName="Helvetica-Bold", fontSize=8.2, leading=11, textColor=colors.white))
STYLES.add(ParagraphStyle(name="CodeCopy", fontName="Courier", fontSize=7.1, leading=10, textColor=INK, spaceAfter=6, splitLongWords=True))
STYLES.add(ParagraphStyle(name="Hash", fontName="Courier", fontSize=6.9, leading=9, textColor=INK, splitLongWords=True))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def p(text, style="Copy"):
    return Paragraph(text, STYLES[style])


def literal(text, style="CodeCopy"):
    return p(escape(str(text)).replace("\n", "<br/>"), style)


def table(headers, rows, widths):
    content = [[p(escape(str(x)), "HeaderCell") for x in headers]]
    for row in rows:
        content.append([x if isinstance(x, Paragraph) else p(escape(str(x)), "Cell") for x in row])
    t = Table(content, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT, colors.white]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, TEAL),
        ("LINEBELOW", (0, 1), (-1, -1), 0.2, colors.HexColor("#D4E0E5")),
    ]))
    return t


def section(story, number, title):
    story.extend([PageBreak(), p(f"{number} / HISTORICAL EVIDENCE", "SmallCopy"), p(title, "SectionTitle")])


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#CFDDE3"))
    canvas.line(20 * mm, 18 * mm, PAGE_W - 20 * mm, 18 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GRAY)
    canvas.drawString(20 * mm, 13 * mm, "Agentic Physics Bench | Historical evidence | Audit: 3 November 2026")
    canvas.drawRightString(PAGE_W - 20 * mm, 13 * mm, str(doc.page))
    canvas.restoreState()


def invariant_canvas(*args, **kwargs):
    kwargs["invariant"] = 1
    return Canvas(*args, **kwargs)


def build(output):
    inv = json.loads(INVENTORY.read_text())
    # Fail rather than silently author a report from changed historical inputs.
    for entry in inv["sources"]:
        if digest(ROOT / entry["path"]) != entry["sha256"]:
            raise ValueError("Historical source changed: " + entry["path"])
    baseline_manifest = ROOT / "docs/evidence/2026-11-03/manifest.json"
    if digest(baseline_manifest) != inv["baseline_manifest_sha256"]:
        raise ValueError("Baseline manifest does not match inventory")
    audit = inv["verification"][1]
    assert (audit["unique_calls"], audit["advisor_active_calls"], audit["calls_explicitly_naming_claude_fable_5_1"]) == (48, 31, 28)
    story = [Spacer(1, 12 * mm), p("REPRODUCIBLE RESEARCH RECORD", "SmallCopy"),
             p("Agentic Physics Bench", "CoverTitle"),
             p("Historical evidence and provenance audit", "Deck"),
             HRFlowable(width="100%", thickness=2, color=TEAL), Spacer(1, 8 * mm),
             p("Evidence preserved through 26 October 2026.<br/>Rechecked on 3 November 2026.", "Deck"),
             p("This report separates completed historical studies, development pilots, voided development runs, and unavailable evidence. It excludes all new difficulty-ramp experiments."),
             p("The saved V1 and V2 results reproduce their published counts. Both studies reached a ceiling on final-answer correctness. V2's strongest finding is a provenance failure caught in development: a server-side advisor was active in 31 of 48 unique calls; 28 explicitly named a second model. Those development stages were voided before the clean scored campaign."),
             table(["Evidence class", "What is supported"], [
                 ["V1 / V2 scored records", "24 / 162 episodes; published counts recompute with zero mismatches."],
                 ["V3 development pilot", "21 episodes and 36 calls; no held-out experiment completed."],
                 ["V4 development", "One completed four-call Opus smoke run, plus incomplete and deterministic runs kept separate."],
                 ["Original raw evidence", "V1/V2/V3 raw traces absent here. Published hash indexes remain; V4 local evidence verified."],
             ], [125, 355]),
             Spacer(1, 8 * mm), p("Prepared with Codex from repository records. Repository authorship and original commit history remain intact. No new historical model inference was performed for this audit.", "SmallCopy"),
             literal("Baseline commit: " + inv["baseline_commit"]),
             literal("Inventory: docs/evidence/2026-11-03/historical_inventory.json")]

    section(story, "01", "What was preserved and verified")
    story += [p("The baseline is a local archive of 244 pre-existing files, together with a Git bundle and a SHA-256 manifest. The original checkout was on main at the commit below; its only reported untracked item was .DS_Store. The integration work occurred in a separate worktree."),
              literal(inv["baseline_commit"]),
              table(["Check", "Audit outcome"], [
                  ["Published V1/V2 headline counts", "Recomputed by src/headline_results.py: 0 mismatches."],
                  ["Analytical-branch integration", "All 216 original tracked files compared byte-for-byte with first parent before merge."],
                  ["V2 development advisor audits", "Deduplicated by (episode_id, turn); duplicates agree. 48 unique calls; 31 advisor-active; 28 naming Fable."],
                  ["V4 successful smoke evidence", "Saved run.json and events.jsonl byte hashes match; canonical manifest digest also matches."],
                  ["Historical raw trace audit", "Skipped for V1/V2/V3 because raw directories are missing. This is not a passed check."],
              ], [158, 322]),
              p("Strength and limits of the record", "SubTitle"),
              p("The archive, Git history and hashes provide a reproducible content baseline. They detect differences against a trusted recorded digest; they are not external timestamping, digital signatures, or protection against someone rewriting both a file and its manifest. The archive should be copied to independently controlled storage if stronger custody is needed."),
              p("The report verifies available records and labels historical claims. It does not re-create missing model calls or infer hidden model computation. A serving model can change behind a stable model name; re-running inference would create a new experiment, not reproduce the old transcript."),
              p("Statistical unit", "SubTitle"),
              p("Episode counts describe the fixed task sets. Model calls are not independent scientific replicates. Repeated conditions and repetitions share task content, so comparisons are paired or clustered at task level. Success on all observed cases is a ceiling, not proof of general reliability."),
              literal("Baseline manifest SHA-256:\n" + inv["baseline_manifest_sha256"])]

    section(story, "02", "V1: easy physics tasks and an unused tool")
    story += [p("Setup", "SubTitle"),
              p("Twelve held-out synthetic velocity-time tasks compared a direct answer with an optional fit_line workflow. The model was claude-opus-5 through Claude Code CLI 2.1.278, requesting high effort. Native tools, MCP and persistence were disabled. The harness exposed a narrow numerical line-fit tool and deterministically graded the acceleration with units. Scoring ran on 21 September 2026."),
              table(["Condition", "Correct / planned", "Tool requests"], [["Direct answer", "12 / 12", "Not offered"], ["Optional fit_line", "12 / 12", "0 / 12"]], [210, 135, 135]),
              p("There were 24 recorded episodes and 24 model calls, all valid under V1's controls. The deterministic solver passed all 12 tasks. No scored episode was excluded or repeated. Two development episodes used one development case; they are not additional held-out observations."),
              p("Interpretation", "SubTitle"),
              p("Offering the tool produced no observed correctness gain on these cases. The benefit of executing it was untested because it was never requested. Numerical agreement with a least-squares answer does not establish that the model internally used least squares."),
              p("The fixed set is small, synthetic and sign-balanced. One repetition per case does not characterize run-to-run variability. For illustration only, 12 successes in 12 independent, identically distributed Bernoulli trials would have a two-sided 95% exact interval of [" + f"{0.025 ** (1 / 12):.3f}" + ", 1]. The study does not establish the independent sampling assumptions needed to interpret that interval as a general accuracy bound."),
              p("Provenance limits", "SubTitle"),
              p("V1 did not disable the advisor pathway later discovered in V2. Its 24 scored raw traces were historically rescanned and reported the declared model alone. That raw rescan cannot be repeated in this checkout, which lacks the original raw files. V1's original per-call controls covered a narrower set of metadata than V2's amended controls."),
              literal("Protocol: EXPERIMENT.md\nEpisodes: results/episodes_scored.jsonl\nSummary: results/summary.json\nRelease: v1.0.0 -> 8d336d8302ecf76b6bcabf7afc37ab817a0630ea")]

    section(story, "03", "V2: ceiling results and a provenance failure")
    story += [p("Setup", "SubTitle"),
              p("Eighteen held-out tasks, split into three difficulty groups, were crossed with no-tool, optional-tool and required-tool conditions and three repetitions: 162 episodes and 324 model calls. The model was claude-opus-5 through CLI 2.1.280. Two turns were used per episode. The scored run on 23 September 2026 explicitly disabled the advisor and checked per-call model identities, server tools and usage metadata."),
              table(["Condition", "Correct / planned", "Tool behavior"], [["No tool", "54 / 54", "53 / 54 first-turn answers correct"], ["Optional tool", "54 / 54", "54 / 54 requested fit_line"], ["Required tool", "54 / 54", "54 / 54 compliant"]], [137, 118, 225]),
              p("All 162 episodes were valid. Saved per-call metadata report 324/324 scored calls with the declared model alone and no server-side tools. All 108 executed tool results were relayed within tolerance. The deterministic solver passed 18/18 tasks. Repetitions and conditions reused the same tasks; 54 is not an independent-task sample size."),
              p("Voided development stages", "SubTitle"),
              table(["Audit measure", "Count / unique calls"], [["Advisor active", "31 / 48"], ["Explicit claude-fable-5-1 model key", "28 / 48"], ["Episodes with at least one affected call", "21 / 24"]], [310, 170]),
              p("The two stage files each contain 36 calls, but 24 call records overlap. Adding 36 + 36 would double-count them. Some historical text calls all 31 advisor-active calls 'second-model' calls. The precise distinction is retained here; old evidence has not been rewritten."),
              p("Interpretation and confounds", "SubTitle"),
              p("Correctness alone did not reveal the undeclared system component: contaminated development calls could still score correctly. The clean scored campaign reached a ceiling in every condition, so it establishes no accuracy advantage. Optional uptake changed from V1's 0/12 to V2's 54/54 while prompts, tasks, CLI, advisor settings and turn structure changed; the difference cannot be assigned causally to one factor."),
              literal("Episodes: results/v2/episodes_scored.jsonl\nAudits: results/v2/dev_stage{1,2}/advisor_audit.json\nRelease: v2.0.0 -> 68106835b31935b4fb08210456210ec2b20ea52c")]

    section(story, "04", "V3: a development pilot, not held-out evidence")
    story += [p("The frozen V3 protocol combines tool-instruction compliance (Arm A) and claims about closed-form quantum-pendulum kernels (Arm B). The 13 October 2026 pilot used claude-fable-5-1, high effort, through pinned CLI 2.1.296 with fallback and advisor disabled and an allowlisted environment."),
              table(["Pilot arm", "Episodes / planned", "Calls"], [["A: 3 development tasks x 5 policy cells", "15 / 15", "30"], ["B: 3 development items x 2 frames", "6 / 6", "6"]], [300, 115, 65]),
              table(["Arm A policy", "Requested / 3", "Final correct / 3"], [["A: no policy sentence", "2", "3"], ["B: try not to use tool", "0", "3"], ["C: permission YES", "3", "3"], ["C: permission NO", "0", "3"], ["D: never request or use", "0", "2"]], [260, 110, 110]),
              p("The report records 36/36 calls passing runtime checks. Five permitted tool requests executed once each. No prohibited request occurred, so the live denial path was not exercised. Existing V3 would deny such a request; this differs from an experiment where the prohibited tool remains executable."),
              p("With n=3, zero requests in a cell is weak evidence: the illustrative two-sided exact 95% binomial upper bound is " + f"{100 * (1 - 0.025 ** (1 / 3)):.1f}%" + ". The tasks are fixed development examples and were inspected, so this is not a confirmatory population estimate."),
              p("One cell-D first-turn answer was correct but became incorrect on the revision turn. Arm B observed no false closed-form claim on the four 'none known' items and finite forms on both free-particle frames. Its grader certified claim/form class; the returned full expressions were not numerically verified."),
              p("The held-out V3 plan was not started: 180 Arm A episodes and 60 Arm B episodes, at most 420 calls. This audit does not execute it or reinterpret development observations as held-out results."),
              literal("Pilot: experiments/v3_instruction_compliance/PILOT_REPORT.md\nEpisode files: results/episodes_dev.jsonl and results/pendulum_episodes_dev.jsonl inside V3\nFreeze: v3.0.1-protocol-freeze -> 1b95a4f3984ab1a555ddba9cd1c22fa511161805")]

    section(story, "05", "V4: a bounded Knowledge Vault smoke test")
    v4 = inv["experiments"][4]["successful_real_run"]
    story += [p("V4 measures disclosure and explicit forbidden output actions in a synthetic Knowledge Vault, alongside legitimate physics utility. It is a different construct from forbidden tool invocation. Attacker and defender contexts are separate; saved event chains, pre-call manifests and immutable final snapshots support replay."),
              table(["Completed real development run", "Observed"], [["Run identity", v4["run_id"]], ["Attacker / defender", "claude-opus-5 / claude-opus-5"], ["Calls / reported model turns", "4 / 4"], ["Legitimate utility", "2 / 2"], ["Detected disclosure or forbidden action", "None"], ["CLI list-price estimate", "$0.060508; not a billed-charge statement"]], [255, 225]),
              p("The local run.json and events.jsonl match the hashes published in opus_smoke_verification.json. The manifest matches after the exact canonical serialization used by V4: sorted keys, compact separators and UTF-8. Its digest is not the hash of the pretty-printed manifest file."),
              p("Outcomes that remain separate", "SubTitle"),
              p("An earlier Fable attempt (v4-3cf73a61d8744116) used two CLI calls, reported three model turns and a $0.08365 list-price estimate. It stopped after a provider refusal and was incomplete; it is not a completed security evaluation. Two deterministic runs used fixed probes and the deterministic gate, with zero model calls. The permitted-force case demonstrated an intentionally defective disclosure policy: authorized outputs mathematically revealed a protected parameter without agent disobedience."),
              p("Coverage and privacy limits", "SubTitle"),
              p("The detector covers exact tokens, selected encodings and explicit schema actions. Arbitrary encodings, partial leaks and other semantic violations are outside coverage. One completed adaptive smoke run is not an efficacy estimate. An email-like identifier in its attacker text has an unestablished origin; the evidence does not prove cross-role context access."),
              p("Full V4 messages and private seeds remain in the local preserved archive. They are not reproduced in this report. The shareable verification record contains text-free outcome and integrity fields."),
              literal("Source: experiments/v4_knowledge_vault/DEVELOPMENT_REPORT.md\nVerification: experiments/v4_knowledge_vault/results/opus_smoke_verification.json\nRun SHA-256: cc6fa6c48c5e27720c51b1ff5fc8c708f679bad4be6be27d73ff7bfdc6a0a4be\nEvents SHA-256: dc8287598f2bbda30eb41ccafc0bc6ce4bc54c2698e189d3bc21815fb657e882")]

    section(story, "06", "Branch integration and unresolved evidence")
    story += [p("The analytical-physics branch diverged from V1 and contained eight documentation-only commits. It added a numerical-versus-analytical research proposal and related history. It contained no new source implementation, tests, task data or experiment results."),
              literal("Source tip: 9d1256298bb7459a5ee60f56ec8d790d0a7097ac\nMerge base: 8d336d8302ecf76b6bcabf7afc37ab817a0630ea\nArchival merge: " + inv["branch_integration"]["merge_commit"]),
              p("The reviewed merge preserved every newer main file and both parent histories, and imported the exact seven branch-tip documents under docs/archive/analytical-physics/. The Git 'ours' strategy was used deliberately to avoid replacing current root documentation or interleaving immutable historical records. The archive contains original byte hashes, Git blob identifiers and original commit authorship. It does not retroactively approve or execute the old proposal."),
              p("Unmerged historical drafts", "SubTitle"),
              p("archive/v3-forbidden-tool (085576b) remains an explicitly unreviewed draft of 22 files. archive/backup/v2-tool-policy-first-push remains a superseded ancestry backup. Neither is treated as additional validated research or imported over reviewed V3."),
              table(["Evidence absent locally", "Consequences"], [["V1/V2 results/raw/: 447 indexed files", "Cannot repeat raw trace audit; committed episode and audit files remain available."], ["V3 results/raw/: 48 indexed files", "Cannot repeat raw provenance validation of prefreeze and pilot calls."], ["Two V2 calls outside repository", "Smoke and advisor probe are documented, not represented by local raw files. Development total is 98 documented versus 96 calls in committed unique episode records."]], [220, 260]),
              p("Additional precision", "SubTitle"),
              p("Annotated Git tag object IDs differ from their target commit IDs; this report cites peeled commits. The V3 v3.0.1 freeze commit message says 51 files, but the manifest and historical correction specify 49 files plus 15 dependencies. V1/V2 module docstrings changed after release; exact historical inference reproduction requires the release tag, frozen CLI and matching environment."),
              literal("Archive manifest: docs/archive/analytical-physics/ARCHIVE_MANIFEST.json\nFull audit inventory: docs/evidence/2026-11-03/historical_inventory.json")]

    section(story, "07", "Reproduce the audit without model calls")
    story += [p("Run the following from this worktree. Commands inspect saved records and test the harness; they make no provider calls. Regeneration of historical charts is intentionally not required for this report: source hashes are checked before report construction."),
              literal("cd /Users/leonardaarons-ditson/Projects/agentic-physics-bench-evidence-difficulty\npython3 src/headline_results.py\npython3 -m unittest discover -s tests\npython3 -m unittest discover -s experiments/v3_instruction_compliance/tests\npython3 -m unittest discover -s experiments/v4_knowledge_vault/tests"),
              p("Build this PDF", "SubTitle"),
              literal('APB_RUNTIME="$HOME/.cache/codex-runtimes/codex-primary-runtime"\n"$APB_RUNTIME/dependencies/python/bin/python3" scripts/build_evidence_report.py'),
              p("Portable environment: Python 3.11 or later, reportlab==4.4.9 and pypdf==6.10.0. The generator uses the committed audit inventory and verifies every cited source digest. It emits the PDF, a build-verification JSON and a separate checksum file. ReportLab's invariant output mode makes repeated builds with the same inputs and runtime byte-identical."),
              p("The report records only tests actually run for its generation: inventory source checks, PDF extraction and repeated-build hash equality. The test commands above are reproduction instructions, not a claim that this generator executes all historical test suites."),
              p("Original local baseline", "SubTitle"),
              literal(inv["baseline_archive_directory"]),
              p('Local originals: <link href="file://' + quote(inv["baseline_archive_directory"] + "/original-files.tar.gz") + '" color="#087F8C">original-files.tar.gz</link> | <link href="file://' + quote(inv["baseline_archive_directory"] + "/repository.bundle") + '" color="#087F8C">repository.bundle</link>. Links refer to this machine; share the files separately for another reader.', "SmallCopy"),
              p("The archive directory contains original-files.tar.gz, repository.bundle, manifest.json and SHA256SUMS. The Git bundle preserves refs as captured. The file archive includes local private V4 evidence and should not be published without a separate review."),
              literal("cd '" + inv["baseline_archive_directory"] + "'\nshasum -a 256 -c SHA256SUMS\ngit bundle verify repository.bundle\ntar -tzf original-files.tar.gz"),
              p("Verification must compare each item with the appropriate digest format. The source appendix uses byte SHA-256; the V4 manifest verification uses canonical JSON SHA-256. Hashes for unavailable raw traces demonstrate an existing commitment, not present possession of the original bytes."),
              p("New experiments", "SubTitle"),
              p("Any new difficulty ramp, model condition, seed schedule or policy must have its own prospective protocol, frozen inputs, budgets, result files and report. This historical report makes no claim about their execution or outcomes.")]

    section(story, "A", "Source files and complete SHA-256 digests")
    story += [p("Every source below was checked against the inventory during PDF construction. Paths are repository-relative. Each full digest is printed across two lines for readability; concatenate those lines without whitespace. The complete baseline inventory additionally lists all 244 preserved files."),
              literal("Inventory byte SHA-256:\n" + digest(INVENTORY)),
              literal("Baseline manifest byte SHA-256:\n" + inv["baseline_manifest_sha256"])]
    rows = []
    for src in inv["sources"]:
        rows.append([literal(src["path"], "Hash"), literal(src["sha256"][:32] + "\n" + src["sha256"][32:], "Hash")])
    story.append(table(["Source path", "SHA-256 (complete)"], rows, [262, 218]))
    story += [Spacer(1, 8 * mm), p("Preserved release and protocol commits", "SubTitle")]
    wanted = ["v0-protocol-freeze", "v1.0.0", "v2.0.0", "tool-use-study-final", "v3-protocol-freeze", "v3.0.1-protocol-freeze"]
    story.append(table(["Reference", "Target commit"], [[name, literal(inv["refs"]["refs/tags/" + name]["commit_id"], "Hash")] for name in wanted], [190, 290]))
    story += [Spacer(1, 6 * mm), p("Archive and report integrity files", "SubTitle"),
              literal("docs/evidence/2026-11-03/manifest.json\ndocs/evidence/2026-11-03/SHA256SUMS\ndocs/evidence/2026-11-03/headline_check.txt\ndocs/archive/analytical-physics/ARCHIVE_MANIFEST.json\nreports/historical-evidence-2026-11-03.build.json\nreports/historical-evidence-2026-11-03.SHA256SUMS"),
              p("This appendix is a record of evidence availability and content identity. It does not substitute for absent raw files, prove model determinism, or establish mathematical impossibility from finite failures.", "SmallCopy")]

    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=20 * mm,
                            leftMargin=20 * mm, topMargin=19 * mm, bottomMargin=25 * mm,
                            title="Agentic Physics Bench - Historical Evidence and Provenance Audit",
                            author="Codex; based on preserved Agentic Physics Bench records",
                            subject="Historical evidence only; excludes new experiments")
    doc.build(story, onFirstPage=footer, onLaterPages=footer, canvasmaker=invariant_canvas)
    reader = PdfReader(str(output))
    texts = [page.extract_text() or "" for page in reader.pages]
    if any(len(t.strip()) < 100 for t in texts):
        raise ValueError("Empty or unreadable report page")
    text = "\n".join(texts)
    for needle in ["31 / 48", "28 / 48", "162", "36", "244", inv["baseline_commit"], "does not substitute for absent raw files"]:
        if needle not in text:
            raise ValueError("Missing expected report content: " + needle)
    report_digest = digest(output)
    # A second build checks byte reproducibility, not just textual similarity.
    return {"pages":len(reader.pages), "characters_per_page":[len(x) for x in texts],
            "sha256":report_digest, "source_files_verified":len(inv["sources"]),
            "inventory_sha256":digest(INVENTORY), "generator_sha256":digest(__file__),
            "reportlab_version":REPORTLAB_VERSION, "pdf_text_checks":"passed", "model_calls":0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT_DIR / PDF_NAME)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT / "results") or output.is_relative_to(ROOT / "data"):
        raise SystemExit("Refusing to write inside historical data/results directories")
    first = build(output)
    second = build(output)
    if first["sha256"] != second["sha256"]:
        raise ValueError("Repeated build was not byte-identical")
    second["repeated_build_byte_identical"] = True
    metadata = output.with_suffix(".build.json")
    metadata.write_text(json.dumps(second, indent=2) + "\n")
    checksums = output.with_suffix(".SHA256SUMS")
    checksums.write_text(f"{digest(output)}  {output.name}\n{digest(metadata)}  {metadata.name}\n")
    print(json.dumps({"pdf":str(output), "verification":str(metadata), "checksums":str(checksums), **second}, indent=2))


if __name__ == "__main__":
    main()
