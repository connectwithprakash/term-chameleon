# Adversarial Audit — Ranked Change Spec

**Repo:** `.` (v0.1.1, branch `main`)
**Date:** 2026-06-27
**Nature:** Read-only audit. This report IS the spec; it changes nothing.
**Scope:** Documentation hygiene only. Zero source code, test, CI, or packaging changes are proposed. All targets are repo-root and `docs/` markdown/text artifacts.

---

## 1. TL;DR

| Metric | Count |
|---|---|
| Proposals considered | 30 |
| **Survived** (adversarially verified) | **19** |
| Rejected (recorded, do not re-litigate) | 11 |

**Distinct survivors after de-duplication:** the 19 survivors collapse to **~7 real actions** (several survivors are the same merge re-proposed from different angles).

**Single biggest recommendation:**
> **Get the 10-file root audit pile out of the repo root and under version control in one move.** Today the root holds a single-session audit dump (10 ALL-CAPS `.md`/`.txt`/`.py` files), 9 of which are **untracked** working-tree scratch (verified: `git status` shows `??` for all but `STRESS_TEST_FINDINGS.md`). Nothing in source, CI, `pyproject.toml`, `README`, or `CONTRIBUTING` references any of them (verified: repo-wide grep returned `NO_REFS_IN_SOURCE_CI`). The single highest-leverage action is to **consolidate the redundant renderings, then relocate the durable survivors into a tracked `docs/audit/` subtree** — this simultaneously fixes clutter, duplication, and the "valuable findings live in untracked scratch" hazard.

**Confidence:** High. Blast radius is near-zero across every survivor — no load-bearing reference into this doc cluster exists outside the cluster itself.

---

## 2. Surviving Changes — ranked by leverage, grouped by type

Ranking favors changes that (a) reduce the most duplication/drift, (b) bring untracked value under version control, and (c) carry the lowest blast radius. Several survivors below are **the same underlying action** re-derived from different proposals; they are noted as such so the executor does not double-count.

### A. AGGREGATE / de-duplicate (highest leverage — kills drift)

**A1. Merge the 4 audit-prose files into one canonical remediation doc** ⭐ top leverage
- **Targets:** `AUDIT_SUMMARY.md` + `IMPLEMENTATION_PLAN.md` + `IMPLEMENTATION_QUICK_START.md` + `FIX_MATRIX.txt`
- **Change:** Keep `IMPLEMENTATION_PLAN.md` as the detailed body (it alone carries before/after code blocks, exact line numbers, verification procedures). Fold `AUDIT_SUMMARY.md` in as an exec/header section and `IMPLEMENTATION_QUICK_START.md` + `FIX_MATRIX.txt` in as a checklist/matrix appendix. Delete the three redundant renderings.
- **Standard:** DRY / single source of truth. All four describe the identical 25-issue / 5-phase audit; `FIX_MATRIX.txt` is `QUICK_START` re-typeset in box-drawing ASCII; `AUDIT_SUMMARY` restates the same five phases. Their cross-references form a closed loop pointing only at each other.
- **Confirmed drift (this is the live hazard):** headline effort total disagrees across files — `IMPLEMENTATION_PLAN.md:6` says **35-45 hours**, while `AUDIT_SUMMARY.md:6` says **45-57 hour project** (both verified by direct read). ASCII charts elsewhere say 46-59h. This is exactly the inconsistency one source eliminates.
- **Blast radius:** Effectively zero. All four are untracked (`??`). No tracked file, `.py`, or CI references any. Only cross-refs are intra-cluster and collapse into the survivor. Reconcile the effort total during the merge so the canonical doc states one number.
- **REJECTED sub-branch:** do **not** replace these with `docs/audit-findings-*.json`. The JSONs are a different, larger corpus (85 raw findings across 4 rounds) lacking the prose set's phase grouping, effort estimates, and roadmap. Not a superset; not an equivalent rendering.

**A2. Merge the 4 edge-case files into one findings doc** ⭐ high leverage
- **Targets:** `ADVERSARIAL_EDGE_CASES.md` + `EDGE_CASE_FINDINGS_SUMMARY.md` + `EDGE_CASE_QUICK_REFERENCE.md` + `EDGE_CASE_ANALYSIS_INDEX.md`
- **Change:** Keep `ADVERSARIAL_EDGE_CASES.md` (the detailed superset). Fold in the `QUICK_REFERENCE` severity matrix + one-line fixes as a top section, and `FINDINGS_SUMMARY`'s per-finding fixes + phase plan + open design questions. **Delete `EDGE_CASE_ANALYSIS_INDEX.md` entirely** (pure table-of-contents over its own siblings; adds navigation overhead, no unique findings). Delete `FINDINGS_SUMMARY` and `QUICK_REFERENCE` after folding.
- **Standard:** DRY for docs. Same 12 edge cases / 3 CRITICAL recur across all four at four zoom levels.
- **Blast radius:** No external references (grep clean). Internal mutual cross-links in the survivor must be rewritten as in-document anchors. `EDGE_CASE_TEST_SCENARIOS.py` is referenced by name but is **not** a deletion target and is untouched.
- **Executor caveat (load-bearing):** "keep at most a short severity table" must NOT be read so literally that the roadmap, one-line-fix catalog, and open design questions get dropped. The `QUICK_REFERENCE` severity matrix + copy-paste fixes are the lowest-friction operational artifact and exist in no other file — **fold, do not discard.** (A narrower proposal that tried to delete `QUICK_REFERENCE` as "navigation overhead" was REJECTED for this reason.)

**A3. Merge the 2 stress-test reports into one**
- **Targets:** `STRESS_TEST_FINDINGS.md` (tracked) + `EXTREME_STRESS_TEST_SUMMARY.txt` (untracked)
- **Change:** Keep the **tracked** `STRESS_TEST_FINDINGS.md`, fold in the `.txt`'s finer 12-category per-test breakdown, delete the `.txt`.
- **Standard:** One test run = one source-of-truth report. Both document the identical run (`tests/test_extreme_stress.py`, 44/44 pass, 6.56s, commit `158a8a9`, same benchmark table).
- **Blast radius:** Near-zero. `.txt` is untracked; only reference is its own "Files Generated" self-listing. The lone external mention is an incidental filename string inside `docs/audit-findings-round2-2026-06-27.json` (names the `.md`, not the `.txt`) — not a link.
- **Executor caveat (carryover bug, see §3):** the `.txt`'s 12-category counts sum to **46**, but the run is **44** tests, and the `.md`'s own 8-row coverage matrix sums to 44. **Reconcile to 44 when folding** — do not import the 46 error into the tracked file. This is a *reconcile-and-rewrite*, not a clean delete; the "pure plaintext re-render" justification is partly false, but the merge survives on dedup merits.

### B. MOVE-CONTENT (relocate durable knowledge into a tracked home)

**B1. Relocate the consolidated audit/edge-case/stress docs into a tracked `docs/audit/` subtree** ⭐ (the headline recommendation)
- **Targets:** the surviving consolidated docs from A1/A2/A3 (durable prose subset; **not** `EDGE_CASE_TEST_SCENARIOS.py`).
- **Change:** `git mv` / `git add` the survivors into `docs/audit/` (e.g. `docs/audit/audit-remediation-plan.md`, `docs/audit/edge-cases.md`, `STRESS_TEST_FINDINGS.md`), alongside the existing tracked `docs/audit-findings-*.json`, `product-spec.md`, `implementation-plan.md`, `testing-strategy.md`.
- **Standard:** repo-established — `docs/` is the version-controlled home; root holds only entry-point docs (README, CHANGELOG, CONTRIBUTING, LICENSE). The 10 root files are the same artifact class as the tracked `docs/audit-findings-*.json`.
- **Blast radius:** Low. 9/11 originally-targeted files are untracked (plain `mv` + `git add`). Zero inbound path-resolving references. One stale prose filename mention inside `docs/audit-findings-round2-2026-06-27.json` (a quoted audit subject in a JSON `reasoning` string, not a link) is non-load-bearing and unaffected.
- **MANDATORY collision fix:** root `IMPLEMENTATION_PLAN.md` vs existing `docs/implementation-plan.md` are the **same name** on case-insensitive macOS APFS. The destination MUST disambiguate (e.g. `docs/audit/audit-remediation-plan.md`). Do **not** flatten into `docs/`.
- **Destination-shape note (honest):** the repo's existing convention is *flat dated filenames* in `docs/` (`audit-findings-...-2026-06-27.json`), not dated subfolders. `docs/audit/` is a mild invention but keeps the mutually-referencing cluster together; `docs/audits/2026-06-27/` was also proposed and is acceptable but slightly less consistent. Either keeps artifacts together and out of root.

### C. RENAME (disambiguation)

**C1. Rename root `IMPLEMENTATION_PLAN.md` to a job-announcing stem**
- **Targets:** root `IMPLEMENTATION_PLAN.md` vs `docs/implementation-plan.md`
- **Change:** Rename to `audit-remediation-plan.md` (or `remediation-plan.md`). The root file is a dated one-time audit fix-list (PHASE 1 CRITICAL security, 25 issues, effort estimates); `docs/implementation-plan.md` is the durable milestone build plan (Milestone 0..9). Different jobs, effectively identical names.
- **Standard:** a filename should announce its job and not collide with a sibling. On case-insensitive filesystems the only disambiguator today is the directory.
- **Blast radius:** 5 inbound plain-text mentions in untracked siblings (`FIX_MATRIX.txt:231,261`, `AUDIT_SUMMARY.md:278,319`, `IMPLEMENTATION_QUICK_START.md:285`) must be updated in the same change. No source/CI/`pyproject` reference. `docs/implementation-plan.md` has zero inbound refs and is untouched.
- **Note:** This rename is **subsumed by A1 + B1** if executed together (the file gets renamed *and* relocated in the consolidation). Treat C1 as standalone only if A1/B1 are deferred. Do **not** bundle an unverified `docs/audits/2026-06-27/` path into the rename if doing it standalone — the rename stem is warranted; the specific directory is a separate decision.

### D. CONFORMANCE (reconcile contradictions to a single truth)

**D1. Reconcile divergent effort/issue numbers across the audit cluster**
- **Targets:** `IMPLEMENTATION_PLAN.md`, `AUDIT_SUMMARY.md`, `FIX_MATRIX.txt`, `EDGE_CASE_ANALYSIS_INDEX.md`, `docs/audit-findings-*.json`
- **Change:** Pick one canonical effort/issue figure and apply it consistently; fix the **intra-file** arithmetic contradictions; explicitly label the audit-family (25 issues) and edge-case-family (12 issues, 6-8h) as **distinct audits with distinct totals**.
- **Self-contradictions verified (these are arithmetic defects, not scope differences):**
  - `IMPLEMENTATION_PLAN.md:6` header "35-45 hours" vs its own phase subtotals (8-10 + 10-12 + 10-12 + 12-15 + 5-8) = **45-57**.
  - `AUDIT_SUMMARY.md:6` "45-57 hour project" vs its own chart total `:222` "46-59h".
  - `FIX_MATRIX.txt:3` "45-57 Hours" vs its own total `:184` "46-59h".
  - JSON rounds are arrays of length 37/20/12/16 (=85 raw) and never reconcile to the prose "25 actionable" — no dedup mapping documented.
- **Standard:** single internally-consistent source of truth; a reader cannot currently tell if the project is 35-45, 45-57, or 46-59 hours.
- **Blast radius:** Pure planning-doc edits, no code/test dependency.
- **Note:** **Largely absorbed by A1** (the merge forces one number). D1 matters as a standalone only for the JSON-rounds note and the edge-case "distinct audit" label, which the prose merge does not touch.

**D2. Mark stale root prose as superseded by the dated, verified JSON rounds**
- **Targets:** root prose audit docs vs `docs/audit-findings-round{1-4}-2026-06-27.json`
- **Change:** Treat the dated JSON (rounds 1-4, with per-finding `verdict` blocks) as source of truth for *findings status*; either retire the root prose or add a dated "superseded" header. Prefer the **header variant over deletion** to preserve intra-cluster links.
- **Substantive contradiction verified:** `AUDIT_SUMMARY.md:20` asserts "No crashes, **no memory leaks**", but `docs/audit-findings-round2-2026-06-27.json:74` is a VERIFIED finding documenting an unbounded in-memory `events` list in `watch_live.py:143` (appended every loop, ~1-2 GB/year) and quotes the summary's false claim verbatim. The JSON supersedes the prose on a real technical point.
- **Blast radius:** Contained to the cluster. README/CHANGELOG/`pyproject.toml` reference no audit artifact (grep clean).
- **Note:** If A1+B1 are executed, the prose merge + relocation already removes most of this hazard; D2's residual value is the explicit "JSON is current truth on findings status" framing.

### E. SPLIT (additive — new governance/index files)

**E1. Add `SECURITY.md` at repo root**
- **Change:** Dedicated `SECURITY.md` — supported versions, vulnerability reporting/disclosure channel, threat model — alongside existing `CONTRIBUTING.md`.
- **Standard:** GitHub community-health file; security disclosure is a distinct concern from data-safety (README "Safety principles" covers only backups/`--dry-run`) and contribution mechanics. Grep confirms **zero** disclosure/vulnerability-reporting language anywhere.
- **Blast radius:** Additive; breaks nothing. GitHub surfaces it under the Security tab.
- **CRITICAL content-accuracy caveat (see §3):** do **not** claim hardening that is not shipped. The proposal's suggested "0o700 perms" line is false — source still uses `0o755` in `iterm_api.py:92`, `terminal_pattern.py:26`, `install.py:166`, `watch_daemon.py:240`. The threat-model section must track actual source state and reference the open findings, not assert un-merged fixes.

**E2. Add `docs/README.md` index**
- **Change:** Index the 10 tracked `docs/` files (3 prose design docs, `research/` ×3, 4 audit-findings JSON rounds at 37/20/12/16 findings), noting what each covers and that each JSON round maps to its resolving fix commit (`af8a318`/`9133840`/`c4b2e3d`/`0213389`).
- **Standard:** a docs index surfaces info invisible from `ls` (116KB+ of JSON, round semantics). No index exists today; the only index file (`EDGE_CASE_ANALYSIS_INDEX.md`) is untracked and indexes root, not `docs/`.
- **Blast radius:** Minimal additive — one new file, no references break.
- **Executor caveat:** mark the audit rounds as **resolved/historical** (each maps to a fix commit), not pending work, or the index misleads.

---

## 3. Carryover facts & live bugs (surfaced by the audit; NOT fixed here)

These are real technical findings discovered during verification. This audit does not touch source; flagging for the source-fix backlog and for accurate `SECURITY.md` content.

1. **Unbounded memory growth** — `watch_live.py:143`: `events` list appended every loop iteration, returned only after run completes (10-yr default duration) → ~1-2 GB/year. Directly contradicts `AUDIT_SUMMARY.md`'s "no memory leaks" claim. (Verified finding, `audit-findings-round2.json:74`.)
2. **World-readable script perms still shipped** — `0o755` in `iterm_api.py:92`, `terminal_pattern.py:26`, `install.py:166`, `watch_daemon.py:240` (audit finding #4, unremediated as of v0.1.1).
3. **Unvalidated `--python` executable** — flows `cli.py:136 → 793 → watch_daemon.py:121` into the daemon (finding #2, live).
4. **AppleScript escaping incomplete** — `live_stage.py` added `_escape_applescript_string`, but `iterm_window.py:53` still runs a raw script var with no escaping (finding #1, only partially fixed).
5. **Doc arithmetic errors** — effort totals self-contradict within `IMPLEMENTATION_PLAN.md`/`AUDIT_SUMMARY.md`/`FIX_MATRIX.txt`; the stress `.txt` per-category counts sum to 46 vs the actual 44 tests. Reconcile during A1/A3/D1.

---

## 4. Rejected-and-why (ledger — do not revisit)

| # | Proposal | Why rejected |
|---|---|---|
| R1 | Collapse 4 edge-case docs keeping ONLY `ADVERSARIAL` (delete other 3) | Mis-scoped (real set is 5, incl. `EDGE_CASE_TEST_SCENARIOS.py`); "identical 12 findings/IDs" premise false (docs use divergent local vs global IDs; `QUICK_REFERENCE` has a 12th LOW finding `SUMMARY` lacks); `QUICK_REFERENCE`'s severity matrix + one-line fixes are unique and would be lost. **Note:** the *corrected* version of this merge IS survivor A2 (fold, don't drop). |
| R2 | Reconcile edge-case family + full-audit family into one ledger (demote edge-case to feeder) | False subsumption premise. `min_luminance_delta` validation, atomic-write *recovery* (HIGH-4), classification off-by-ones, region negative-coord validation, tiny-image percentile sampling are all ABSENT from the audit (0 hits). Real overlap is only ~3 of 12. Demotion would bury findings existing nowhere else. Warranted fix is narrower: reconcile severity/fix/effort for the ~3 overlapping rows only. |
| R3 | Move `EDGE_CASE_TEST_SCENARIOS.py` into `tests/` (or fold into doc) | Not a green suite: collects 65, **5 fail by design** (adversarial bug-spec with "Should be:" comments, expects ValueErrors the code never raises). Moving it under `testpaths=["tests"]` reds CI. Not illustrative-only either (65 live-import cases). It's an audit specimen; the "docs reference `tests/test_edge_cases_*.py`" claim is a future-placement *instruction* in its own docstring, not a broken link. |
| R4 | Rename `ADVERSARIAL_EDGE_CASES.md` to `EDGE_CASE_AUDIT.md` / `docs/audit/edge-cases.md` | Conditional on an aggregation not yet applied. Today it's one member of a 5-doc cluster with a distinct "deep-dive" role; `FINDINGS_SUMMARY` already owns the findings-summary job. Rename would collide with that role and with `AUDIT_SUMMARY.md`. "Adversarial" is consistent cluster vocabulary, not incidental. (After A2 the survivor gets relocated/renamed via B1 anyway.) |
| R5 | Asymmetric "drop the `.txt`" stress merge with no content migration | Premise "txt is pure re-render" false — `.txt` carries a 12-category breakdown, git commit anchor, "AREAS TESTED" PASS verdicts, and CI recommendations not in the `.md`. A one-sided delete = info loss. **Note:** survivor A3 is the corrected version (fold the breakdown in first, reconcile the 46-vs-44 count). |
| R6 | Move `EDGE_CASE_TEST_SCENARIOS.py` → `tests/test_edge_cases.py` so pytest collects it | Same as R3 from a different angle: untracked scratch, 5 intended-failing cases, duplicates coverage already in tracked tests, encodes aspirational assertions. Wrong verb (rename) for untracked redundant output; correct disposition is delete/ignore or selectively port after diffing. |
| R7 | Relocate the whole 10-file family to `docs/` citing CONTRIBUTING as the "one home" policy | Wrong boundary (real set is 11 incl. the `.py`); **fabricated anchor** — `CONTRIBUTING.md` mentions `docs/` nowhere; would break bare-filename pointers; relocates duplication without dedup. **Note:** the *corrected* version (dedup first via A1/A2/A3, THEN relocate survivors, exclude the `.py`) is survivor B1. |
| R8 | Add `docs/audit/README.md` summarizing each JSON round's findings + resolution status | JSONs are NOT raw/uninterpretable — each finding is self-describing with structured `verdict` blocks; resolution status already lives in git (4 rounds → 4 named fix commits). A prose README would duplicate git history and drift. (Distinct from survivor E2, which indexes the *whole* `docs/` dir at a navigation altitude, not per-finding resolution status.) |
| R9 | Collapse 4 edge-case docs to "at most two" deleting INDEX + QUICK_REFERENCE | Bundles a warranted deletion (INDEX) with an unwarranted one (QUICK_REFERENCE's unique severity matrix + paste-ready fixes) under a false "navigation overhead" label. The INDEX-only deletion is correct and is folded into survivor A2. |
| R10 | Fold edge-case + 25-issue prose into the JSON corpus as single source of truth | Grounding false: claimed overlaps (Kitty detection, color clamp, AppleScript injection) have ZERO matching JSON findings. The round2 JSON's own verifier treats the prose as a prior baseline it *extends*. Corpora hold different facts → nothing to dedup; folding would drop prose-only CRITICAL security items. |
| R11 | Move `EDGE_CASE_TEST_SCENARIOS.py` into `tests/` (third variant) | Same refutation as R3/R6: 5 intended-failing cases (e.g. `sampled_pixels` semantics the code doesn't implement), untracked scratch, unverified redundancy claim, wrong test count (65 not 69). |

**Pattern across rejections:** every refuted proposal either (a) targeted `EDGE_CASE_TEST_SCENARIOS.py` as a movable/deletable test (it is an intended-to-fail audit specimen — leave it alone), or (b) over-reached a clean dedup into lossy deletion or a false-subsumption merge. The surviving A1/A2/A3 are the disciplined versions of the same instincts.

---

## 5. Ordered execution plan (lowest-risk-mechanical first)

Each wave is independently shippable. Validation notes flag where a cold check is warranted.

**Wave 0 — Additive, zero risk (do first, no dependencies)**
- E1: Add `SECURITY.md` (truthful threat model — see §3 caveat; do NOT claim `0o700`).
- E2: Add `docs/README.md` index (mark JSON rounds as resolved/historical).
- *Validation:* none needed; new files, no references break.

**Wave 1 — In-file conformance fixes (low risk, no moves yet)**
- D1: Reconcile the self-contradicting effort numbers within each audit-prose file; label edge-case family as a distinct audit.
- *Validation:* re-read each edited header against its own phase-sum; confirm one consistent figure.

**Wave 2 — Aggregate / dedup (medium risk — content migration, get migration right)**
- A3: Merge stress reports → keep tracked `STRESS_TEST_FINDINGS.md`, fold `.txt` breakdown, **reconcile 46→44**, delete `.txt`.
- A2: Merge edge-case 4 → keep `ADVERSARIAL_EDGE_CASES.md`, fold matrix/fixes/roadmap/questions, delete INDEX + SUMMARY + QUICK_REFERENCE, rewrite internal links as anchors. Leave `EDGE_CASE_TEST_SCENARIOS.py` untouched.
- A1: Merge audit-prose 4 → keep `IMPLEMENTATION_PLAN.md` body, fold the other three, delete them, drop dangling cross-links, apply the reconciled effort number from D1.
- *Validation (cold-read):* open each surviving doc fresh and confirm no dangling "see other document" links remain and no unique content (one-line fixes, 12-category counts, open questions, code blocks) was dropped. This is the wave most prone to silent info loss.

**Wave 3 — Rename + relocate (medium risk — path/collision surgery, do last)**
- C1 + B1 together: rename root `IMPLEMENTATION_PLAN.md` survivor to `audit-remediation-plan.md` AND relocate all Wave-2 survivors into `docs/audit/`. `git mv` the tracked `STRESS_TEST_FINDINGS.md`; `git add` the (formerly untracked) survivors so the durable knowledge enters version control.
- D2: While relocating, confirm the dated JSON rounds remain the findings-status source of truth; if any prose is kept verbatim rather than merged, add a "superseded" header.
- *Validation (cold check, MANDATORY):* on the case-insensitive macOS default FS, verify NO collision between the relocated `audit-remediation-plan.md` and `docs/implementation-plan.md` (must NOT flatten to `docs/`). Run `git status` to confirm survivors are now tracked and nothing in source/CI/`pyproject`/README broke (re-run the repo-wide grep — expect still-clean).

**Why this order:** Waves 0-1 touch no file relationships and can ship immediately. Wave 2 changes content and must precede relocation so you move clean, deduped survivors (not 10 redundant files) — this is also the corrected form of rejected R7. Wave 3 is the only wave with a real filesystem/collision hazard, so it goes last and gets the cold check.

---

*Confidence: high on blast-radius (verified zero external references), high on the dedup grounding (files read directly), medium on exact line numbers cited from the audit's own notes where not independently re-opened. The source-code bugs in §3 are real and out of scope for this doc-hygiene spec — route them to the engineering backlog.*
