# Inspections PWA — Handover Document

**Date:** 29 April 2026
**Version:** v261
**Previous:** v260
**Model:** Opus 4.7
**Status:** Brief BUILD COMPLETE on screen. All 7 sections live, polished, renumbered sequentially. **PDF page-breaks STILL BROKEN** at handover — three attempts in this thread, none clean. Hand off in a known-broken state on PDF only.

---

## 1. READ THIS FIRST — current state

**Live and clean on SCREEN at `/analytics/site-meeting-brief`:**
- §01 Project Status (with inspection scope as 3rd grey line)
- §02 De-snag Results
- §03 Fortnight Movement (renumbered from §04)
- §04 Defect Pool (renumbered from §05)
- §05 Defects by Zone (renumbered from §06)
- §06 Findings (renumbered from §07)
- §07 Worst Units (renumbered from §09)

Sequential 01–07 with no gaps. Confirmed rendering correct on screen.

**PDF: BROKEN.** Multiple attempts at page-break rules in this thread produced inconsistent output:
- Attempt 1: `page-break-inside: avoid` on `.section` + `page-break-after: avoid` on `.section-header` → caused §04 header to disappear from page 2, §05 overline orphaned on page 2, page count grew from 3 to 4
- Attempt 2 (revert + .section-tight class on small sections + page-break-before on §05) → operator reports "still fucked up" — DO NOT attempt patch-on-patch. **REVERT and start clean.**

---

## 2. PDF page-break — REVERT FIRST, REDESIGN SECOND

The damage trail is in `app/templates/analytics/site_meeting_brief.html`:
- `.section-tight` CSS rule was added
- §02, §03, §06, §07 section openers had ` section-tight` appended to their class
- A `<div style="page-break-before: always; break-before: page;"></div>` was inserted just before §05's overline `{% if mode != 'live' %}` block

**Step 1 — revert ALL page-break edits to baseline:**
```python
import re
path = 'app/templates/analytics/site_meeting_brief.html'
with open(path) as f: c = f.read()
# remove .section-tight rule
c = c.replace("\n.section-tight { page-break-inside: avoid; break-inside: avoid-page; }", "")
# remove ' section-tight' from class lists
c = re.sub(r'class="section section-tight', 'class="section', c)
# remove forced page break before §05
c = c.replace('    <div style="page-break-before: always; break-before: page;"></div>\n', '', 1)
with open(path, 'w') as f: f.write(c)
```

Verify with `grep -n "section-tight\|page-break-before" app/templates/analytics/site_meeting_brief.html` — expect 0 matches. Commit revert as its own commit.

**Step 2 — redesign approach (do not implement until operator confirms direction):**

The right approach is probably **fixed page assignments**, not avoid-rules. Three pages:
- Page 1: §01, §02, §03 (already fits cleanly per first PDF)
- Page 2: §04 (Defect Pool chart) + §05 (Zone grid) — needs to be tested whether they fit together
- Page 3: §06 (Findings) + §07 (Worst Units)

Implement as `page-break-before: always` on §04 and §06 specifically (NOT §05). Keep all other CSS untouched. Test the PDF after each ONE edit — do not bundle.

**DO NOT** add any `page-break-after: avoid` rules — they caused header disappearance.
**DO NOT** add `page-break-inside: avoid` to `.section` — too strict for tall sections.

---

## 3. WHAT GOT BUILT THIS THREAD (pre-PDF mess)

### Commit 5 — §05 Defect Pool (deployed, verified)
- Markup-only addition. SVG line chart with fortnightly trend points + delta labels. Reuses `trend_points`, `svg_open`, `chart_w`, `chart_h` from existing data dict. CSS for `.legend-item`, `.trend-placeholder`, `.section svg text` lining-numerals rule added.

### Commit 6 — §06 Defects by Zone (deployed, verified, restyled, recoloured)
- Markup-only addition. Block × Floor grid reusing `zone_grid` + `floor_labels`. Then iteratively restyled to match operator's mockup:
  - **Restyle pass 1**: compact 1-line top-of-cell header (`X units · M inspected`), removed progress bars from de-snag cells, single-line `XX.X% cleared` indicator
  - **Restyle pass 2 (colour)**: neutral text, calmer pastel backgrounds. Awaiting `#FBEFE2`, not-inspected `#ECEAE5`, near-complete `#EBEFDC`, de-snag `#FAEEDA` (unchanged).
  - **Restyle pass 3 (borders + tonal nudges)**: 1px `#DCD7CB` border on every cell + every legend swatch. Awaiting lightened to `#FCF2E5`. Near-complete cooled to `#E9EED7`.

### Commit 7 — §07 Findings (deployed, verified)
- New helper `_build_brief_findings(tenant_id, snapshot_str)` in `app/routes/analytics.py` immediately above `_build_brief_prev_desnag`. Hardcoded 5 buckets matching the verified data:
  1. KEYS not provided — `not provided` (79/25)
  2. CLEANING required (combined) — `to be cleaned`, `needs to be cleaned` (176/34)
  3. WATER not connected for testing — `no water to test operation` (117/15)
  4. PAINT MARKS — `has paint marks` (96/35)
  5. NOT INSTALLED — `not installed` (83/30)
- Sub-detail = top 5 `item_template.item_description` values per bucket. Both routes wired via `data.update(...)`.

### Commit 8 — §09 Worst Units (deployed, verified, then renumbered to §07)
- Markup-only. 5-column table (Unit · Zone · Cycle · Open · Wks since C1). Inline header callout right-aligned: `Worst: 106 (212) · Avg: 63 · Oldest: 11 wks`. Reuses `stuck_units[:5]` + `stuck_headline`. Footer: `Showing top 5 of 115 units with open defects (7,276 total). Per-unit average is 63.`

### Commit 9 — Inspection scope moved to §01
- Removed `<div class="page-footer-scope">` block. Added 3rd `<div class="line">` to §01 status strip with grey `#9A9A9A` colour. The `.page-footer-scope` CSS rule on line ~213 is now dead — harmless, leave it.

### Commit 10 — Three polish items
- `pool_trend.avg_change` thousands separator: `{{ '{:,}'.format(pool_trend.avg_change|int|abs) }}` applied to BOTH branches (grew/shrunk)
- New helper `_strip_leading_zero(date_str)` in routes file. Both brief routes post-process `data['kpi']['est_complete']` after upstream call. `08 May 2026` → `8 May 2026`. Pipeline Report untouched.
- §09 row highlighting removed entirely — `#FFF8F6` background dropped, `#C44D3F` red Open column kept (always red since all top-5 rows exceed avg). Footer simplified to `...Per-unit average is 63.`

### Commit 11 — Sequential renumber 01–07
- Two-phase parking technique to avoid collision (e.g. naive cascade `04→03, 05→04` would re-match the new `04`). Used `@@NN@@` sentinels, then unparked. Old numbers 04, 05, 06, 07, 09 → new 03, 04, 05, 06, 07.

### Commits 12+ — PDF page-break attempts (REVERT THESE)
- See §2 above for what to revert.

---

## 4. KNOWN ISSUES — DEFERRED

1. **Stale `inspection_cycle` reference** in `_build_pipeline_report_data` (active_batches block). Comment vs code mismatch. NOT URGENT.
2. **`snapshot_date_short` data variable** — set in both routes, unused since §02 overline removed. Harmless. May be useful later. Leave.
3. **Brief eventually replaces Pipeline Dashboard "snapshot" mode** — operator's stated direction. Separate workstream.
4. **Defect description cleanup** — v258 §14 deferred workstream. Production data mutation, separate session.
5. **Back/Home navigation** — operator removed Back. May add Home later.
6. **`import_c2_template.py` `cleared_at` timestamp** — uses runtime UTC instead of backdated. Will distort next C2 import snapshot. Per user memories, ongoing flag.

---

## 5. THE BRIEF SHAPE — FINAL

| # | Section | Reuses | Helper |
|---|---|---|---|
| 01 | Project Status | `kpi`, `snapshot_date` | (post-process: `_strip_leading_zero`) |
| 02 | De-snag Results | `desnag` | `_build_brief_prev_desnag` |
| 03 | Fortnight Movement | `ledger`, `pool_trend` | — |
| 04 | Defect Pool | `trend_points`, `svg_open`, `chart_w`, `chart_h` | — |
| 05 | Defects by Zone | `zone_grid`, `floor_labels` | — |
| 06 | Findings | (new query) | `_build_brief_findings` |
| 07 | Worst Units | `stuck_units`, `stuck_headline` | — |

**Cut sections:** §03 (v258 — Inspections Completed), §08 (v259 — Trade Throughput, may return after 8 May).

**Renumbering decision:** sequential 01–07 with no gaps. Operator preferred clean sequence over preserving spec traceability.

---

## 6. KEY FACTS — PROJECT STATE

### Snapshot (29 April 2026)
- Units inspected: 157 / 191 (82%)
- Open defects: 7,276
- Avg defects/unit: 46
- Most defects: 212 in Unit 106 (Block 3 1st Floor)
- De-snag: 75 verified · 42 clear · 56.0% UC · 96.8% DFR · 111 remaining
- Prev fortnight: 58.0% UC · 97.5% DFR
- Fortnight movement: B/Fwd 5,069 · Cleared 1,295 · New 3,502 · Open 7,276 · Pool +2,207

### Production / infra (unchanged from v260)
- Production URL: `https://inspections.archpractice.co.za`
- DB path: `/var/data/inspections.db`
- Repo: `~/Documents/GitHub/inspections-pwa/`
- Tenant: `MONOGRAPH`
- Stack: Flask/Python, SQLite, HTMX, Jinja2, Tailwind, Chart.js, Playwright/Chromium for PDFs
- Workflow: edit on MacBook → push to GitHub → Render auto-deploys
- DB ops: Render console only (Python heredoc, never sed for code)
- Render console paste limit: ~40 lines max for heredoc
- Pipeline Report route: `/analytics/pipeline-report` (UNTOUCHED throughout)
- Site Meeting Brief route: `/analytics/site-meeting-brief` (LIVE)
- Site Meeting Brief PDF: `/analytics/site-meeting-brief/pdf` (page breaks broken)

### Schema — VERIFIED v259, NO CHANGE
- `defect.original_comment` (NOT `description`) — populated 7,276/7,276
- `item_template.item_description` (NOT `item_name`)
- `defect.defect_type` only 3 values, useless as category
- Trade: `defect → item_template → category_template.category_name`
- Area: `category_template.area_id → area_template.area_name`

---

## 7. NEXT-THREAD STARTING PROMPT
---

## 8. RULES STILL IN FORCE (from v251–v260)

- One commit per logical change
- Edit on MacBook, never on Render directly
- No recommendations in any report — facts only
- Show evidence — every claim has a verifiable command + output
- Render console paste limit: ~40 lines max for heredoc
- Inspection items per unit (master template): 509
- Project exclusion list: 55 items applied. Effective inspectable: 454
- Block format: "Block 1", "Block 2", proper case
- Inspection timestamps: `submitted_at` preferred, `created_at` fallback, `strftime('%Y-%m-%d %H:%M:%S')`
- DM Sans + lining numerals for numeric content
- Two-phase parking when renaming colliding values

---

## 9. LESSONS THIS THREAD

1. **Don't bundle CSS rules whose interactions you haven't traced.** The first PDF attempt combined `page-break-inside: avoid` + `page-break-after: avoid` and produced unpredictable output (header disappeared from §04). Each rule should ship + verify alone.
2. **Read failure modes before patching.** When operator said "PDF still broken," I went straight to a third attempt. Should have reverted to baseline and rebuilt from a known-good state.
3. **Two-phase parking is the right pattern for cascade renames.** Sentinels prevent collision. Naive cascade caused the 09→07→06 trap.
4. **`rfind` is brittle for HTML pattern matching.** `<div class="section-header">` contains `<div class="section`. Use stricter regex anchors or specific markers.
5. **Operator distinguishes "still wrong" from "different wrong" sharply.** Failing the same way twice in a row is much worse than failing once. Revert is cheap. Iterating on a broken foundation is expensive.

---

**END OF HANDOVER v261**
