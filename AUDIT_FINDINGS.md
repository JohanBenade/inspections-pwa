# INSPECTIONS PWA — CODE AUDIT FINDINGS REGISTER

**Type:** Read-only logic audit. This register FLAGS suspect logic. It does NOT fix anything.
Fixes are decided separately, finding by finding, on Johan's call.

**Method:** Multi-session. One area per pass, in dependency order. Each finding has a stable ID,
severity, location, the suspect logic, and why it contradicts a documented rule or itself.

**Severity scale:**
- **CRITICAL** — wrong data could ship to Raubex, or a wrong certification could result.
- **HIGH** — wrong UI/state that is visible or recoverable but misleading.
- **MEDIUM** — technical debt that will cause a bug under foreseeable change.
- **LOW** — naming, staleness, cosmetic, documentation drift.

**Confidence tags:**
- `[CONFIRMED]` — verified directly in code visible to the auditor.
- `[FLAG]` — strongly suspected from available evidence; needs the live route file to confirm.

---

## PASS PLAN

| Pass | Area | Status |
|------|------|--------|
| 1 | Status model (batch + unit/inspection statuses, transitions) | **CONFIRMED — closed against route files 18 Jun 2026** |
| 2 | Cycle model (zone-cycle vs unit-cycle remnants) | **IN PROGRESS — 18 Jun 2026** |
| 3 | Carry-forward (cleared defects, prior exclusions, NTS/skip between cycles) | **CLOSED — 18 Jun 2026 (6 findings AF-016..AF-021)** |
| 4 | Exclusion handling (link-copy, block/floor/unit overrides) | not started |
| 5 | Defect lifecycle (raise -> clear -> carry -> re-open) | not started |
| 6 | Certification & PDF (what they read; trust in upstream state) | not started |

---

## SOURCE-ACCESS GATE (read before trusting any finding below)

Pass 1 was performed against only two files that were available in project knowledge:
- `STATUS_FLOWS.md` (documented intent, dated 13 Mar 2026, v1.0)
- `inspection_engine.py` (read-only counts engine)

The authoritative status-SETTING code lives in route files NOT yet available to the audit:
`app/routes/inspection.py`, `app/routes/approvals.py`, `app/routes/batches.py`,
`app/routes/certification.py`, plus `app/services/schema.sql`.

**Consequence:** Pass 1 can verify the documented model against the engine, and surface internal
contradictions, but it CANNOT yet confirm what the running code actually sets. Findings tagged
`[FLAG]` must be confirmed by reading the route files (next session: paste them in, or grant repo
read). Until then they are suspicions backed by evidence, not proven defects.

---

## PASS 1 — STATUS MODEL — FINDINGS

### AF-001 — STATUS_FLOWS.md is stale and self-declares as code-derived [CONFIRMED] — MEDIUM
**Location:** `STATUS_FLOWS.md` L1-4, L123, L147-148
**Suspect:** Document is v1.0 dated 13 Mar 2026, header says "Derived from inspection.py +
approvals.py (verified)." Since then the project has materially changed: unit count moved
191->190 in this doc but your live model is **191 units (Unit 001 deleted 03 Jun 2026)**; the doc
says **"509 items"** (L123) while the live operating model is **509 template / 502-508 inspectable
with the active=1 filter and 6 ground-only items**; default exclusion list is named `fca35779`
(L147) but live work references `69ce0e91`, `57678239`, and others.
**Why it's wrong:** A status-flow reference that is silently stale is worse than none — future
work (and future Claudes) will "verify against" a document that no longer matches reality. This is
the root-cause category you named: definitions were never re-pinned after the model changed.
**Action class (not done):** Re-derive from live route files after Pass 1 completes; version-stamp.

### AF-002 — Dual-write status model with no documented reconciliation [CONFIRMED] — HIGH
**Location:** `STATUS_FLOWS.md` L10-14
**Suspect:** Unit status is stored in TWO places — `inspection.status` AND `batch_unit.status` —
"updated together at each transition." There is no documented invariant check, no single source of
truth, and no handling for the case where they drift out of sync.
**Why it's wrong:** Any code path that updates one but not the other leaves a unit in a split
state. Your known bug history (cleared-defect and exclusion carry-forward) is exactly the kind of
divergence dual-write invites. The engine (`top_inspection`, L75-80) trusts `inspection.status`
as "authoritative current state," while the batch detail UI (per the doc's label table) renders
`batch_unit.status`. **Two readers, two sources, no reconciliation = guaranteed eventual mismatch.**
**Action class (not done):** Decide a single source of truth; make the other a derived/auto value.

### AF-003 — Status vocabulary mismatch between doc, engine, and batch logic [CONFIRMED] — HIGH
**Location:** `STATUS_FLOWS.md` L42-49 vs L106-113; `inspection_engine.py` L42-51
**Suspect:** Three different status vocabularies are in play and they do not line up:
- Inspection statuses (engine STATUS_DISPLAY): `not_started, in_progress, submitted, reviewed,
  approved, certified, pending_followup, paused`.
- The flow diagram (L42-43) maps APPROVED to `pending_followup` **or** `approved` — i.e. two raw
  values mean the same logical state.
- batch_unit statuses in the batch-logic block (L106-113): `signed, reviewed, inspected` — a
  DIFFERENT set of words (`signed` not `approved`; `inspected` not `submitted`).
**Why it's wrong:** `inspection.status='approved'` vs `'pending_followup'` meaning the same thing
is a latent bug magnet — any equality check that tests one value silently misses the other. And the
batch rollup keys off `inspected/reviewed/signed` while inspections emit `submitted/reviewed/
approved`; the word "inspected" is never produced by the inspection flow shown, so the mapping
between the two vocabularies is undocumented and must be happening (or failing) somewhere in
approvals.py.
**Action class (not done):** Enumerate the true status set from the schema/CHECK constraints;
collapse synonyms; document the unit<->batch_unit word mapping explicitly.

### AF-004 — `paused` status exists in engine but is absent from the documented flow [CONFIRMED] — MEDIUM
**Location:** `inspection_engine.py` L50 vs `STATUS_FLOWS.md` L16-49
**Suspect:** The engine knows a `paused` status ("paused — RE-INSPECT (data-loss)", the unit 242
case). The documented unit-status flow has no `paused` node and no transition into or out of it.
**Why it's wrong:** A real production status with no documented entry/exit means no one knows what
is allowed to happen to a paused unit — can it be submitted? reviewed? certified? An undocumented
state is where data-loss recovery cases (like 242) silently slip through review gates.
**Action class (not done):** Add `paused` to the model with explicit allowed transitions, or
formalise it as an inspector-only re-walk lock.

### AF-005 — 'TBD' sentinel for unassigned inspector is a string-magic-value [CONFIRMED] — MEDIUM
**Location:** `STATUS_FLOWS.md` L63-64, L145
**Suspect:** Unassigned inspector is represented by the literal string `'TBD'`, and "is treated as
unassigned (same as no inspector)." So unassigned has TWO representations: NULL and `'TBD'`. The
template guard must test both (`u.inspector_id and u.inspector_id != "TBD"`).
**Why it's wrong:** Every query that filters on assigned/unassigned inspectors must remember to
handle both NULL and 'TBD'. Any one that checks only `IS NOT NULL` will wrongly count TBD units as
assigned. This is a classic source of off-by-N in dashboards and briefs.
**Action class (not done):** Normalise to a single representation (prefer NULL); migrate 'TBD'.

### AF-006 — Batch auto-advance has no floor/guard for `signed_off` & `complete` [FLAG] — HIGH
**Location:** `STATUS_FLOWS.md` L104-116
**Suspect:** The batch target is computed purely from the aggregate of batch_unit statuses
(L106-113), BUT the note at L116 says `signed_off` and `complete` "are set separately via explicit
sign-off actions." So the auto-advance block can compute `batch_target='complete'` when
`all(s=='signed')` — yet `complete` is also supposed to require an explicit action and `closed_at`.
Two independent writers can target the `complete` state.
**Why it's wrong:** If the aggregate function can set `complete` on its own, a batch can close
without the explicit sign-off ever running (so `closed_at` may be NULL on a "complete" batch) — or
the explicit action and the aggregate fight each other. Needs approvals.py to confirm which wins.
**Action class (not done):** Confirm in approvals.py; make one path authoritative for `complete`.

### AF-007 — `removed` batch_units excluded from status calc — unverified for all readers [FLAG] — MEDIUM
**Location:** `STATUS_FLOWS.md` L117
**Suspect:** "`removed` batch_units are excluded from status calculations." This is stated for the
batch rollup, but it is not established that EVERY downstream reader (analytics, briefs,
certification counts, PDF) applies the same `removed` exclusion.
**Why it's wrong:** If the batch status logic excludes `removed` but an analytics query does not,
the two will disagree on unit counts — the kind of silent divergence behind your reconciliation
gaps. This mirrors the `active=1` ghost-template discipline: one filter that MUST be applied
everywhere or counts drift.
**Action class (not done):** Grep all readers of batch_unit for the `removed` filter; confirm
universal application.

### AF-008 — Engine trusts highest-cycle inspection as state; no guard for stale lower cycles [CONFIRMED] — MEDIUM
**Location:** `inspection_engine.py` L75-80, L124-160
**Suspect:** `top_inspection` selects the highest `cycle_number` (tie-broken by `created_at DESC`)
and treats it as "the authoritative current state for a unit." `unit_counts` then computes
everything from that single inspection row only.
**Why it's wrong:** This is correct ONLY if every state-bearing fact was carried forward into the
top-cycle inspection_item rows. Your documented bug history says it sometimes was NOT (cleared
defects and prior exclusions failed to copy into the new cycle). So the engine can confidently
report a "clean" top cycle while the carry-forward that should have populated it silently failed.
The engine is not wrong in isolation — it correctly exposes whatever the carry-forward wrote — but
it provides NO invariant that the top cycle actually inherited prior state. This is the seam where
Pass 3 (carry-forward) will matter most.
**Action class (not done):** Add a carry-forward completeness invariant feeding this engine.

### AF-009 — Item-status set: doc lists 5, engine lines on 4, no 'ok' in line set [CONFIRMED] — LOW
**Location:** `STATUS_FLOWS.md` L125-131 vs `inspection_engine.py` L38, L106
**Suspect:** Documented item statuses: `pending, ok, not_to_standard, not_installed, skipped` (5).
The engine's LINE_STATUSES is the 4 non-ok ones (correct — "Items to Mark" excludes ok). No
contradiction in logic, but the doc never states that `ok` is the only status NOT a line, which is
the actual invariant (`already_ok = total_points - items_to_mark`).
**Why it's wrong:** Minor — but the invariant `already_ok + items_to_mark == total_points`
(engine L159) depends on item status being EXACTLY one of these 5 and nothing else. If any item
ever holds a 6th status (e.g. a future 'na' or a typo'd value), `already_ok` silently absorbs it
and the row still "closes" while hiding a bad value.
**Action class (not done):** Confirm a schema CHECK constraint pins item status to exactly these 5.

---

## PASS 1 — OPEN QUESTIONS FOR NEXT SESSION (need route files)

1. `approvals.py` — confirm the real batch auto-advance code matches L106-113, and resolve AF-006
   (who owns `complete`).
2. `inspection.py` — confirm the dual-write of `inspection.status` + `batch_unit.status` (AF-002);
   find any path that writes one without the other.
3. `schema.sql` — read CHECK constraints to settle the TRUE status vocabulary (AF-003) and item
   status set (AF-009).
4. Confirm whether `approved` and `pending_followup` are genuinely interchangeable or a historical
   accident (AF-003).
5. Grep for `'TBD'` across the codebase to size the AF-005 exposure.

---

## PASS 1 — CONFIRMATION AGAINST ROUTE FILES (18 Jun 2026)

Route files read: `inspection.py` (3031 L), `approvals.py` (2540 L), `batches.py` (2504 L),
`certification.py` (1054 L), `schema.sql` (full). All flags below resolved with file+line evidence.
Method: surgical grep + targeted line reads (token-bounded; full files not loaded into context).

### AF-002 — CONFIRMED REAL — HIGH (was [FLAG])
Dual-write is real and unguarded. `inspection.status` and `batch_unit.status` are written in the
SAME function but as TWO SEPARATE statements with no transaction-level invariant tying them:
- Submit: `inspection.py` L2898 `UPDATE inspection SET status='submitted'` immediately followed by
  L2900 `UPDATE batch_unit SET status='submitted'`. One commit (L2902), two writes. If the second
  throws, the first is already staged — split state on rollback-less paths.
- `batch_unit` is NOT in `schema.sql` at all — it (and `inspection_batch`) live in a migration not
  in the canonical schema file. **The audit's source-of-truth schema is incomplete.** This is its
  own finding (see AF-010).
**Confirmed:** two readers, two writers, no reconciliation. Original AF-002 severity HIGH stands.

### AF-003 — RESOLVED + REVISED — the doc's vocabulary fear was half-right, half-wrong
- `inspection.status` real written set (grep of all `UPDATE inspection SET status`): `in_progress,
  submitted, under_review, reviewed, pending_followup` + schema-declared `not_started, paused,
  approved, certified, closed`. **`under_review` is WRITTEN (`certification.py` L426) but is ABSENT
  from the schema's documented 9-value comment set (schema.sql L150-151).** Schema comment lists 9;
  real value count is 10. Documentation drift confirmed at the schema level.
- The doc's feared `signed/inspected` batch vocabulary: these are **computed display stages**
  (`approvals.py` L159, L191 `stage_order`), NOT status-column writes. `batch_unit.status` actually
  receives only `inspecting, paused, submitted, reviewed` (+ `signed_off` on the batch at L1140).
  So AF-003's "two vocabularies don't align" is REAL but the cause is display-stage vs stored-status
  conflation, not synonym values. `approved`==`pending_followup` synonym fear: both are written as
  distinct `inspection.status` values (L1347 writes `pending_followup`; `approved` written elsewhere)
  — they are NOT interchangeable; they are distinct real states. That part of AF-003 is CLEARED.
- **No CHECK constraint** pins either set (schema.sql has comments only, L150-151, L177-179). The
  vocabulary is enforced nowhere — any typo'd status inserts silently.

### AF-004 — CONFIRMED — `paused` is fully real
Schema columns `paused_at`, `total_paused_seconds` (L161-162); written `inspection.py` L1808
`batch_unit SET status='paused'`. Documented flow still omits it. Stands as MEDIUM doc gap.

### AF-005 — CLEARED — 'TBD' sentinel is GONE from route code
`grep -c TBD` across all four route files = **0**. The 'TBD' magic-value exposure the doc warned of
does not exist in current route code. Either migrated out or never reached these files. CLOSED.
(Caveat: not grepped across templates/services — exposure in those layers unverified, but the
status-setting route layer is clean.)

### AF-006 — CONFIRMED REAL + ESCALATED — `complete` has TWO writers AND a dead auto-advance branch
- Explicit writer: `approvals.py` L1361 `UPDATE inspection_batch SET ... status='complete'` with
  `closed_at` set — the legitimate sign-off path. Correct.
- Auto-advance writer: `approvals.py` L557 `batch_target='complete'` when `all(s=='signed' for s in
  bu_statuses)`. **But `'signed'` is NEVER written to `batch_unit.status` anywhere in the codebase**
  (real writes are `inspecting/submitted/reviewed/paused/removed`). The auto-advance branch tests a
  value that cannot occur -> **this branch is DEAD CODE; auto-advance can never reach `complete`.**
  Likewise L562 tests `'inspected'` and `'signed'` — also never-written values.
- **Net effect:** `complete` is only ever reachable via the explicit L1361 path (good — single live
  owner), but the auto-advance ladder (L557-563) is built on status words the system stopped using.
  This is a zone-cycle -> unit-cycle remnant (the root cause Johan named). FEEDS PASS 2.

### AF-009 — CONFIRMED — item-status set correct but UNENFORCED — escalate LOW -> MEDIUM
`inspection_item` set is exactly the documented 5 (schema.sql L177-179) but declared in a COMMENT,
no CHECK constraint. The engine invariant `already_ok + items_to_mark == total_points` rests on an
unenforced set. A 6th value would be silently absorbed into `already_ok`. Severity raised to MEDIUM.

### AF-010 — NEW — CRITICAL-for-audit — canonical schema.sql is missing live tables
`batch_unit` (89 refs) and `inspection_batch` (the batch parent, written at L1361) do NOT appear in
`app/services/schema.sql`. The audit's declared source-of-truth schema does not describe the tables
that carry batch + unit operational state. Their real columns/constraints are unknown to the audit.
**RESOLVED 18 Jun 2026** — captured live via `sqlite_master` on Render:
- `batch_unit(id, tenant_id, batch_id, unit_id, cycle_id, inspector_id, status DEFAULT 'pending',
  created_at, removed_at, removed_by, removed_reason, exclusion_list_id -> exclusion_list(id),
  UNIQUE(batch_id, unit_id))`. **Carries `cycle_id`** — every batch_unit is pinned to one cycle;
  this is the cycle<->batch join. No CHECK on `status` (confirms AF-006 dead-branch is undetectable).
- `inspection_batch(id, tenant_id, name, notes, status DEFAULT 'open', created_by, created_at,
  updated_at, locked, exclusion_notes, received_date, submitted_at, reviewed_at, approved_at,
  signed_off_at, pushed_at, closed_at)`. No CHECK on `status`.
- **NEW sub-finding AF-010b (MEDIUM):** `inspection_batch` tracks lifecycle TWICE — one `status`
  string AND seven timestamp columns (`received_date..closed_at`). Same dual-representation pattern
  as AF-002 but at batch level: `status='complete'` (approvals L1361) is set alongside `closed_at`,
  with no invariant that the string and the timestamps agree. A batch could hold `status='reviewed'`
  with `closed_at` populated, or vice-versa, and nothing detects it.
- Both tables were grown via `ALTER TABLE` past the canonical `schema.sql` (trailing columns on one
  line). **AF-001 confirmed at the structural level: `schema.sql` is not the live schema.**

---

## PASS 2 — CYCLE MODEL — FINDINGS (18 Jun 2026)

Scope: how `cycle_id` and the denormalized `cycle_number` flow through the route files; zone-cycle
remnants. Live data probed on Render (446 inspections). Method: grep + targeted reads + live PRAGMA.

**Live baseline established (not assumed):** `inspection.cycle_number` EXISTS (denormalized, not in
schema.sql), 446 rows, **0 NULL, 0 drift** from parent `inspection_cycle.cycle_number`. `cycle_number`
is write-once at the 3 INSERT sites and NEVER UPDATEd on `inspection`; parent `cycle_number` is never
UPDATEd either. So the denormalization is currently complete and stable — these findings are about
ABSENT GUARDS and remnant code, not present corruption.

### AF-011 — CONFIRMED — MEDIUM — `cycle_number` denormalized onto child tables, no sync guard
`cycle_number` is duplicated from `inspection_cycle` (the only schema-declared home) onto `inspection`
(446 refs region) AND onto `defect` as `raised_/cleared_/addressed_cycle_number` (122 refs) AND onto
`latent_area_note` as `rectified_at_cycle_number` etc. None of these copies is protected by a trigger
or invariant. Today they agree (proven: 0 drift). The risk is structural: any future code that sets a
child `cycle_number` from a different source than its `cycle_id`'s parent will drift silently, and the
engine/approvals read the denormalized copy (`i.cycle_number`) not the join. **This is the same
dual-representation class as AF-002 (status) and AF-010b (batch lifecycle) — a recurring pattern.**
**Action class (not done):** add an invariant (R-rule) `inspection.cycle_number == parent cycle_number`
to the live invariants gate; same for defect/latent copies. Cheap, closes the whole class.

### AF-012 — CONFIRMED — HIGH — dead auto-advance vocabulary is a zone-cycle remnant (extends AF-006)
The batch auto-advance ladder (`approvals.py` L557-563) branches on `batch_unit.status` values
`'signed'` and `'inspected'` that **no write path ever produces** (real writes: `inspecting,
submitted, reviewed, paused, removed, pending, assigned, not_started`). This is residue from the
zone-cycle status model that was never removed when the unit-cycle model replaced it. Live effect:
the `complete` and `inspected` rungs of auto-advance are unreachable; only the explicit sign-off path
(L1361) can close a batch. Not data-corrupting, but it is dead logic that masks intent and will
mislead the next person who reads it as live. **Root-cause exemplar of the whole audit.**
**Action class (not done):** delete dead branches OR re-point them at real status words — decide which
the batch lifecycle actually intends, then make auto-advance match the writers.

### AF-013 — CONFIRMED — MEDIUM — `batch_unit.status` true vocabulary is undocumented and sprawling
Real `batch_unit.status` values observed across writers + precondition guards: `pending, not_started,
assigned, in_progress, inspecting, paused, submitted, reviewed, removed` (and the never-written
`signed`/`inspected` ghosts from AF-012). The schema has NO column comment and NO CHECK for this set;
`reset_unit` preconditions (`batches.py` L2290) enumerate one subset, the auto-advance another. There
is no single authoritative list. This is the batch-level twin of AF-003 (inspection.status drift).
**Action class (not done):** enumerate the intended set, document it, add a CHECK or invariant.

### AF-014 — CONFIRMED — MEDIUM — `LEFT JOIN inspection_cycle` on a should-be-mandatory FK
`reset_unit` (`batches.py` L2280-2281) resolves `cycle_number` via
`LEFT JOIN inspection_cycle ic ON bu.cycle_id = ic.id`. `batch_unit.cycle_id` is `NOT NULL` and is a
logical FK to `inspection_cycle(id)`, so an INNER join is correct. With LEFT, a `bu.cycle_id` that
matches no cycle yields `ic.cycle_number = NULL`, which then flows into the new `inspection.cycle_number`
(L2433) and into defect-rollback predicates `WHERE raised_cycle_number < ?` (L2397) — silently matching
nothing. No orphan exists today (0 drift proven) but the LEFT join removes the guard that would surface
one. Same pattern likely repeats wherever cycle is joined off batch_unit.
**Action class (not done):** grep all `LEFT JOIN inspection_cycle` off batch_unit; make them INNER, or
add an explicit NULL guard before the value is written onward.

### AF-015 — OBSERVATION (not a defect) — denormalization is currently CLEAN
Recorded for completeness and to bound the above: as of 18 Jun 2026 the cycle denormalization shows
zero NULLs and zero parent-disagreement across 446 inspections. AF-011/014 are PREVENTIVE (guard the
class before it bites), not corrective. No repair is warranted now; an invariant is.

---

## ZONE-KILL SWEEP — FULL app/ + scripts/ INVENTORY (18 Jun 2026)

**Directive from Johan (binding):** Cycles were originally used in a ZONE context (zone-cycles).
The model was later corrected: UNITS go through inspection cycles, not zones. The zone<->cycle link
caused prolonged confusion and must be ELIMINATED, never to return. A cycle is a unit-level construct.

**Method:** `grep -rniI "zone"` across `app/` + `scripts/` (*.py/*.html/*.sql/*.js). 836 hits / 45
files. Every line read and classified. CRITICAL DISTINCTION: the WORD "zone" is not the target; the
zone-as-CYCLE equation is. Most hits are harmless and MUST NOT be touched.

### Classification (all 836 accounted for)

**Bucket A — HARMLESS (~140): `timezone`.** `datetime.now(timezone.utc)`, `tzinfo=timezone.utc`,
`from datetime import timezone`. Pure datetime, zero zone relation. NEVER touch — would break every
timestamp. Appears in all route files + most scripts.

**Bucket B — HARMLESS (majority of remainder): "zone" = block+floor spatial cell.** In `analytics.py`
(373 hits) and ALL analytics templates, "zone" already means a BLOCK+FLOOR grid cell, NOT a cycle —
`zone_grid`, `zone_avg`, `zone_score`, "Defects by Zone", "Zone-Adjusted Ranking". This MATCHES the
corrected model (analytics keys on block+floor+unit, never cycle). Cosmetic naming, not the bug.
Renaming = high-risk churn for zero correctness gain — OUT OF SCOPE per no-needless-change discipline.
(Optional Phase-2 cosmetic rename only if Johan wants vocabulary purity; not a fix.)

**Bucket C — THE TARGET: "zone" = a CYCLE. Two files, live code. THIS is the zone-cycle link.**
- **AF-Z1 (HIGH) — `approvals.py` L94-195** pipeline builder. Docstrings state it literally: L94
  "grouped by batch, with zones (cycles) nested inside"; L109 "Get zones (distinct cycles)". Iterates
  distinct `cycle_id` and names each a `zone`; builds `zone['stage']` from the dead
  `signed/inspected/received` vocabulary (the AF-012 ladder); rolls batch up as "worst zone" (L189-195).
  Zone-cycle equation INTACT, driving the live approvals pipeline. KILL: rename construct to `cycle`,
  drop "zone" terms, reconcile stage ladder with AF-012 (real status words).
- **AF-Z2 (HIGH) — `certification.py` L887-980** review-queue grouping. L887 "grouped by batch and
  zone"; L953 `zone_key = (block, floor, cycle_id)`; L955 `zone_name = '{} {} C{}'`. Hybrid binding a
  CYCLE into a spatial key — drags cycle back into zone grouping. KILL: regroup explicitly (block+floor
  for spatial; cycle for cycle); remove `zone` hybrid naming.
- Minor C tails: templates `approvals/pipeline.html` (`b.zones`, "sign off zones") and
  `certification/my_reviews.html` (`batch.zones`) CONSUME the Bucket-C dicts — they change WITH
  AF-Z1/Z2 (rename dict key `zones`->`cycles` end to end). `batches.py` L2061-2103 (`batch_zones`
  header) is block+floor spatial = Bucket B (harmless), NOT a target.

**Bucket D — DEAD SCRIPTS (ignore): `scripts/patch_hotspot_footers.py`, `patch_dashboard_v2.py`,
`dashboard_function_v2.py`.** Old one-off patch scripts; Render runs only committed app code (SOP).
"zone" there is spatial anyway. No action.

### Kill order (when Johan green-lights execution, fresh thread)
1. **AF-Z1** `approvals.py` pipeline — biggest live surface + ties to AF-012 dead ladder. First; one
   PR. Rename `zone`->`cycle` through the function AND template `pipeline.html` together.
2. **AF-Z2** `certification.py` review queue + `my_reviews.html` — one PR.
3. Re-grep `"zone"` after each PR; confirm Bucket C drops to 0 while Buckets A/B untouched.
DO NOT touch analytics.py / analytics templates (Bucket B) or any `timezone` (Bucket A).

---

## REGISTER LOG
- Pass 1 opened. 9 findings (AF-001..AF-009): 0 CRITICAL, 3 HIGH, 4 MEDIUM, 1 LOW, 1 HIGH-flagged.
  Based on STATUS_FLOWS.md + inspection_engine.py only. Route-file confirmation pending.
- Pass 1 CLOSED 18 Jun 2026 against route files. Resolutions: AF-002 confirmed HIGH; AF-003 split
  (vocabulary-drift confirmed, `under_review` undocumented [10th value], synonym-fear cleared);
  AF-004 confirmed; AF-005 CLEARED (no 'TBD' in routes); AF-006 confirmed + escalated (dead
  auto-advance branch on never-written `'signed'`); AF-009 escalated LOW->MEDIUM (unenforced set);
  AF-010 NEW (schema.sql missing `batch_unit`/`inspection_batch`). Tally now: 1 audit-CRITICAL
  (AF-010), 3 HIGH, 5 MEDIUM, 0 LOW. AF-001 (stale doc) unchanged — root cause, deferred to Phase 2.
- Pass 2 OPENED + worked 18 Jun 2026 (cycle model). Live baseline: 446 inspections, cycle_number
  denormalized, 0 NULL / 0 drift. 5 entries: AF-011 (cycle_number denorm, no sync guard, MEDIUM);
  AF-012 (dead zone-cycle auto-advance vocab, HIGH, extends AF-006); AF-013 (batch_unit status
  vocabulary undocumented/sprawling, MEDIUM); AF-014 (LEFT JOIN on mandatory cycle FK, MEDIUM);
  AF-015 (observation: denorm currently clean — guards preventive not corrective). RECURRING THEME
  across passes: dual-representation without invariant (status AF-002, batch AF-010b, cycle AF-011).
  Highest-leverage fix = add R-rule invariants for each dual-rep pair. Pass 2 cycle-flow core done;
  remaining Pass-2 surface (carry-forward of cycle context between cycles) overlaps Pass 3.
- ZONE-KILL SWEEP run 18 Jun 2026 per Johan directive (kill zone<->cycle link permanently). 836 hits
  / 45 files classified. Bucket A timezone (~140, harmless), Bucket B spatial block+floor "zone" in
  analytics (majority, harmless/correct), Bucket C THE TARGET = `approvals.py` L94-195 (AF-Z1, HIGH)
  + `certification.py` L887-980 (AF-Z2, HIGH) where zone literally == cycle, Bucket D dead scripts
  (ignore). Kill = 2 PRs (AF-Z1 first, ties to AF-012). Analytics + timezone OUT OF SCOPE. Audit
  remains read-only; execution awaits Johan green-light in a fresh thread.

---

## PASS 3 — CARRY-FORWARD (cleared defects, prior exclusions, NTS/skip between cycles) — FINDINGS

**Worked 18 Jun 2026** against the live route files `app/routes/inspection.py` (3031L) and
`app/routes/batches.py` (2504L) — same revisions as the Pass-1/2 bundle (line counts match).
Read-only. Carry-forward engine is concentrated at `inspection.py` L97-301 (inspection-start
carry block), L1104-1215 (`add_defect`), L1256-1387 (`clear_prior_defect` / `reopen_prior_defect`),
L1503-1542 (`_update_item_status_from_priors`), and `batches.py` L2280-2441 (`reset_unit` rollback).

### AF-016 — CRITICAL — [FIXED 18 Jun 2026, PR #6] "prior" is defined TWO incompatible ways in the same flow
**Location:** `inspection.py` L112-116 (carry lookup) vs L246, L1122, L1173, L1515, L1522 (defect prior checks)
**Suspect:** The item carry-forward finds the previous inspection by **sequential cycle number**:
`WHERE i.unit_id = ? AND i.cycle_number = ?` with `cycle['cycle_number'] - 1` (L114-116).
Every defect-level "prior vs current" test instead keys on **cycle IDENTITY**:
`raised_cycle_id != ?` / `raised_cycle_id = ?` (L246 prior-defect flag, L1122 dup-block,
L1173 submitted-dup, L1515/L1522 status updater). These two definitions only agree when a unit's
cycles are strictly sequential, 1:1, and every intermediate cycle has an inspection row.
**Why it's wrong:** If a unit ever has a gap in `cycle_number` (a C2 inspection never created, or a
cycle deleted by `reset_unit` outcome A/C at L2423 leaving the next cycle as N while the last real
one was N-2), the L114 lookup for `cycle_number - 1` returns **NULL**. `prev_inspection` NULL ->
`prev_item_map` empty (L160 guard) -> EVERY item silently carries as `pending` (L222/L229 fresh
path) — the unit looks like a brand-new inspection, losing all prior ok/skip carry. Meanwhile the
DEFECT layer (keyed on cycle_id identity, L246) still correctly flags `has_prior_defects` from the
real earlier cycle. Result: **item statuses say "fresh C-N" while defects say "carried from C-(N-2)"
— a split-brain unit.** This is the structural root of the carry-forward bug class Johan has hit.
**Evidence of reachability:** `reset_unit` outcome A (L2331-2335) and C (L2343-2348) both DELETE the
inspection row (L2423) without renumbering; a subsequent cycle increments `cycle_number`. The gap is
producible by normal operator action, not just data corruption.
**Action class (not done):** Make the carry lookup find the most-recent PRIOR inspection by
`cycle_number < current ORDER BY cycle_number DESC LIMIT 1` (matches the engine's own `top_inspection`
pattern at L37), NOT `= current - 1`. Then prior-item and prior-defect layers agree on one definition.

### AF-017 — HIGH — NTS-comment carry-forward is DEAD CODE; intent silently unrealized
**Location:** `inspection.py` L200 (guard) vs L222-227 (else-branch comment keep)
**Suspect:** The "start fresh" else-branch (L222) contains the ONLY code that preserves a prior
comment into the new cycle: L227 `comment = prev['comment'] if status in ('not_to_standard',
'not_installed') else None`. But L222 is reached only when NOT (`cycle_number > 1 and prev_item_map`)
— i.e. when `prev_item_map` is EMPTY. L224 then does `prev = prev_item_map.get(template_id)` on an
empty map, so `prev` is ALWAYS None, so L225 `if prev:` is ALWAYS false, so L226-227 NEVER execute.
For any real C2+ with a previous inspection, control goes to L200, where L211-214 maps prior
`not_to_standard`/`not_installed` to `status='pending', comment=None` — **dropping the comment.**
**Why it's wrong:** Two contradictions in one place: (a) the L226-227 branch is structurally
unreachable (dead), and (b) the live L211-214 branch DISCARDS the prior NTS description. A unit that
failed an item in C2 with a detailed defect note arrives in C3 as a bare `pending` with no carried
context — the inspector re-walks blind. Note this is partially mitigated because the *defect* row
survives in the `defect` table (L246 flags `has_prior_defects`), but the inspection_item.comment
itself is lost, and any UI reading item.comment shows nothing.
**Action class (not done):** Decide intent. If carrying NTS comments forward is desired, move the
keep-logic into the live L211-214 branch. If not, delete the dead L224-227 branch so the next reader
isn't misled into thinking comments carry.

### AF-018 — HIGH — `reopen_prior_defect` cross-cycle guard vs `reset_unit` rollback are asymmetric
**Location:** `inspection.py` L1354-1360 (guard) vs `batches.py` L2370-2380 (rollback reopen)
**Suspect:** `reopen_prior_defect` REFUSES (abort 409) to reopen a defect whose `cleared_cycle_number`
differs from the current cycle (L1358-1360) — "a clearance from an earlier cycle is legally recorded,
must not be destroyed." Correct and protective. BUT `reset_unit` with `markings='reset'` reopens
defects purely by `cleared_cycle_id = ?` for the cycle being reset (L2379) with NO such cross-cycle
legal-record guard, AND the broader L2387-2395 update clears `addressed_cycle_number` on ALL b/fwd
defects with `raised_cycle_number < current`. So the inspector-facing path protects prior-cycle
clearances while the batch-management reset path can roll them back.
**Why it's wrong:** Same logical operation (un-clear a defect) has a hard legal guard in one entry
point and none in the other. If `reset_unit` is run on a cycle-N unit, it reopens N's clearances
(correct) but the L2387 sweep also touches `raised_cycle_number < N` rows — b/fwd defects raised in
EARLIER cycles — stripping their `addressed_cycle_number`. Whether that is intended "de-snag rollback"
or an over-broad reach depends on the de-snag model; the asymmetry with L1358 says at least one of the
two is wrong about how sacred prior-cycle state is.
**Action class (not done):** Reconcile the two reopen paths against ONE rule for prior-cycle
clearance immutability. Confirm on live data whether any unit has `addressed_cycle_number` set on a
defect with `raised_cycle_number < its latest cycle` that a reset would wrongly clear.

### AF-019 — MEDIUM — exclusion carry depends on a 4-deep fallback chain with a known-polluted source excluded
**Location:** `inspection.py` L89-95, L126-156 (excl resolution), L171-193 (skip-vs-carry gating)
**Suspect:** Whether an item is `skipped` (excluded) in the new cycle is resolved through: (1)
`inspection.exclusion_list_id` if set (L128-130); (2) else re-read `batch_unit.exclusion_list_id`
and back-fill inspection (L132-141); (3) if a list found, skip its items (L142-147); (4) if NO list,
ZERO exclusions — `cycle_excluded_item` is DELIBERATELY NOT consulted (L148-153, v417, "polluted by
2026-05-19 cleanup script"). Layered on top, L171-193 has two override gates (`_prev_for_skip` pending,
`_null_reason_born_skip`) that intentionally DON'T skip even a listed item under follow-up conditions.
**Why it's wrong:** This is the rule-5 link-copy gap (units 014/015/016/227/252/269/248 already bit)
turned into code: the ONLY robust exclusion source is `exclusion_list_id` correctly present on either
`inspection` or `batch_unit`. If both are NULL (the exact pre-created-without-link case the skill's
Exclusion Architecture section warns about), the unit gets ZERO skips — every excluded item becomes a
live `pending` the inspector must MS/NTS. Not data-corrupting (fails OPEN, not closed) but it silently
shifts inspection burden and diverges per-unit depending on whether the link was copied. The v354/v417
override gates are evidence this has been patched reactively multiple times rather than from one model.
**Action class (not done):** Confirm on live data how many current-cycle inspections have BOTH
`inspection.exclusion_list_id` IS NULL AND `batch_unit.exclusion_list_id` IS NULL for a unit that
should be excluded. Decide whether NULL-link should hard-fail the start instead of failing open.
**Live probe (23 Jun 2026, Render, read-only):** active-cycle inspections with BOTH `inspection.exclusion_list_id` NULL AND `batch_unit.exclusion_list_id` NULL = **0**. Fails-open exclusion gap is NOT manifesting on any live unit. Risk remains LATENT (a future NULL-link start would still fail open). No data fix required now.

### AF-020 — MEDIUM — auto-resolve orphan-parent sweep (L251-301) runs only on cycle start, never re-evaluated
**Location:** `inspection.py` L251-301 (three UPDATE sweeps), all gated `if cycle_number > 1`
**Suspect:** On C2+ start, three sweeps auto-flip `pending` parent/child items to `ok`: orphan parents
with no non-skipped children (L252-269), children of Rule-3 parents (L272-286), and Rule-3 parents
themselves (L290-301). These run ONCE at inspection creation. If exclusions later change mid-cycle
(Raubex emails Kevin a change — a documented workflow), or a child item is un-skipped after start, the
parent's auto-ok is never recomputed.
**Why it's wrong:** The auto-ok decision is a point-in-time snapshot taken before any inspecting
happens. The domain explicitly allows exclusions to change between rounds; if a change lands after a
unit's C-N inspection is created but before it's submitted, the parent-rollup `ok` can be stale (parent
marked ok because all children were skipped at start; a child later un-skipped leaves parent wrongly ok).
**Action class (not done):** Verify whether any code path re-runs these sweeps on exclusion change, or
whether parent rollup is recomputed at submit/review. If not, the auto-ok is a stale snapshot.
**Live probe (23 Jun 2026, Render, read-only):** C2+ in_progress inspections with an `ok` parent above a live (non-skipped, non-ok) child = **0** (tightened from a broad 890-row count that conflated C1 [no sweep runs] and normal in-progress work). The sweep's stale-snapshot failure is NOT present on any live unit. Risk remains LATENT (an exclusion change landing after C2+ start could still leave a parent wrongly ok). No data fix required now.

### AF-021 — LOW — cross-file timestamp format inconsistency (isoformat 'T' vs space)
**Location:** `inspection.py` L72 etc. (`datetime.now(timezone.utc).isoformat()` -> 'T' separator) vs
`batches.py` L2262 (`.strftime('%Y-%m-%d %H:%M:%S')` -> space separator)
**Suspect:** The inspection flow writes ISO-8601 with a 'T' date/time separator; `reset_unit` writes a
space-separated format. Both land in the same timestamp columns (`created_at`, `updated_at`,
`cleared_at`) on the same tables.
**Why it's wrong:** Mixed string formats in one column make lexicographic ORDER BY and string-range
predicates (`WHERE created_at < ?`) unreliable across rows written by different paths, and any
downstream `fromisoformat()` parse will reject the space variant (Python <3.11). Not currently
data-corrupting but a latent sort/parse hazard. NOTE: `reset_unit` L2432 `now.split(' ')[0]` is
CORRECT for its own space format (verified) — this finding is about the inconsistency BETWEEN files,
not a bug within reset_unit.
**Action class (not done):** Standardise on one format (recommend `.isoformat()` everywhere) when next
touching either file.

---

### PASS 3 TALLY
6 findings: **1 CRITICAL (AF-016)**, 2 HIGH (AF-017, AF-018), 3 MEDIUM (AF-019, AF-020), 1 LOW (AF-021).
AF-016 is the structural root of the carry-forward bug class (split definition of "prior").
AF-014 (Pass 2, LEFT JOIN inspection_cycle, batches.py L2283) is REAFFIRMED here — same reset_unit
function — and compounds AF-016: a NULL cycle_number from the LEFT join would corrupt the very
sequential-number lookup AF-016 relies on.

### RECURRING THEME (now spans 3 passes)
Pass 1/2: dual-representation without an invariant (status, batch, cycle).
Pass 3 adds: **dual-DEFINITION without an invariant** — "prior" means cycle_number-1 in one layer and
cycle_id-identity in another, with nothing forcing them to agree. Same disease, different axis.

### REGISTER LOG (append)
- Pass 3 worked 18 Jun 2026 against inspection.py + batches.py (live route files). 6 findings
  AF-016..AF-021: 1 CRITICAL, 2 HIGH, 3 MEDIUM, 1 LOW. AF-016 (split "prior" definition) is the
  carry-forward root cause. AF-014 reaffirmed + compounds AF-016. Read-only; no fixes. Theme extends:
  dual-definition without invariant. Pass 3 CLOSED.

---

## EXECUTION LOG

### AF-016 — FIXED & DEPLOYED — 18 Jun 2026 (PR #6, commit 1391ef8)
**Change:** `inspection.py` L112-116 prev_inspection lookup changed from exact-predecessor
(`cycle_number = ? [current-1]`) to most-recent-prior (`cycle_number < ? ORDER BY cycle_number
DESC LIMIT 1`), mirroring engine top_inspection (L37). Item-layer and defect-layer now share one
definition of "prior".
**Pre-deploy live verification (Render, read-only):** NULL cycle_number=0; units with cycle gaps=0
(fix is PURELY PREVENTIVE, zero existing units affected); 1 in_progress C2+ (unit 267, 509 items,
past start block, untouched by deploy).
**AI-review bot suggestion REJECTED with evidence (twice):** bot urged `AND i.removed_at IS NULL`;
PRAGMA table_info(inspection) proved NO `removed_at` column exists (21 cols, removal not tracked on
inspection — that's a batch_unit pattern). Adding it would crash every C2+ start. Advisory-only,
non-gating; correctly overridden.
**Deploy note:** stray `fix_af016 (1).py` (duplicate browser download) was accidentally committed,
caught by AI-review bot, removed via fresh branch fix/af016-clean (force-push hung repeatedly this
session — new-branch + plain push is the reliable workaround).
**Post-deploy (Render, new pod ...gbkzs):** check_invariants_live ALL PASS — R1=0/0, R2=1/1
(ghost 1161cc67), R3=0/0. Baselines unmoved. CLOSED.

### R4 INVARIANT — ADDED & DEPLOYED — 18 Jun 2026 (AF-016 regression guard)
**What:** New invariant rule R4 = "cycle-number sequence gap". Counts distinct units whose
inspection.cycle_number values are not a contiguous run min..max (or have NULL). A gap is exactly
the AF-016 divergence condition (old cycle_number-1 lookup vs most-recent-prior fix). Zero gaps =>
the item-layer and defect-layer "prior" definitions provably agree. Baseline 0.
**Files (4, one PR):** invariant_rules.py (rule_R4_cycle_number_gap + RULES entry + LIVE_BASELINES),
check_invariants_live.py (BASELINES R4=0 + comment), tests/test_invariants.py (import + counts_for
+ CLEAN/DIRTY asserts), tests/fixtures/build_fixtures.py (planted gap: unit-C cycles {1,3}).
**Tested:** CI gate CLEAN (0,1,0,0) / DIRTY (1,2,1,1) PASS locally + on Mac. Live runner ALL PASS.
**AI-review bot: 3 flags, ALL rejected with evidence:** (1+3) `removed_at IS NULL` on inspection —
no such column (PRAGMA proven, 21 cols); (2) cycle_number-resets-per-cycle — disproven live: 0 units
have a repeated cycle_number across cycle_ids, range 1..3, so cycle_number IS per-unit-monotonic
(also re-confirms AF-016 soundness).
**Deployed:** new pod ...pnbg9, check_invariants_live ALL PASS incl R4=0/0. CLOSED.

### DEPLOY ENVIRONMENT NOTE (for SOP_DEPLOY.md)
This session: `git pull` and `git push --force-with-lease` HANG silently (remote pre-fetch stalls).
`git push` on a FRESH branch works reliably. Workaround when a branch needs rewrite: create a NEW
branch + plain push, abandon the old one. Also: `git checkout main` reconciles to origin without a
pull (local main was already in sync after the push). Recommend adding to SOP gotchas.

### AF-019 + AF-020 — LIVE PROBES RUN — 23 Jun 2026 (read-only, no fix)
Both MEDIUM carry-forward findings probed against live data on Render Shell.
- **AF-019** (NULL-link fails-open exclusion): 0 active-cycle inspections with both `inspection.exclusion_list_id` and `batch_unit.exclusion_list_id` NULL. Live-clear.
- **AF-020** (stale auto-ok parent snapshot): 0 C2+ in_progress inspections with an `ok` parent above a live non-skipped/non-ok child. Live-clear. (A naive probe returned 890 by including C1 inspections, where the sweep never runs, and normal partial in-progress work; tightening to C2+/in_progress isolated the true population -> 0.)
**Outcome:** both findings are LATENT-ONLY. Code can still produce each failure under its documented trigger (future NULL-link start; exclusion change after C2+ start), but neither has bitten any live unit. Johan's call on whether to harden (AF-019: hard-fail NULL-link start; AF-020: re-run sweep at submit/review) or leave as accepted latent risk. Read-only; no code or data changed this session.
