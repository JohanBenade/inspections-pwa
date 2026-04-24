# Inspections PWA — Handover Document
**Date:** 24 April 2026
**Version:** v246
**Previous:** v245
**Model:** Opus 4.7
**Status:** Production **GREEN**. Major session: briefing PDF hardened for scale + nav restructure + role access widening. 10 commits pushed. SR-013 and SR-012 both render clean. Pipeline snapshot vs live reconciliation pending.

## 1. ONE-LINE SUMMARY

Merged briefing pages 3+4 → button reset → threshold-based open-item format → running header via Playwright (fixes page 7 overflow + all orphans) → Batch Reports nav rolled out to team_lead/manager/admin → Home/Analytics links cleaned up → inspector_audit Home link removed.

## 2. WHAT SHIPPED

| # | Commit | File(s) |
|---|--------|---------|
| 1 | Merge pages 3+4 into single "Defects by area and trade"; renumber downstream | briefing.html |
| 2 | Download PDF button resets after 5s | briefing.html |
| 3 | Threshold-based open-item format; drop redundant de-snag lists | briefing.html |
| 4 | **Playwright running header on every physical page** | pdf_playwright.py, analytics.py (route), briefing.html |
| 5 | Batch Reports nav visible to team_lead/manager/admin (desktop+mobile) | base.html |
| 6 | Hide Home link for team_lead/manager/admin | base.html |
| 7 | Remove Analytics top-nav link + Pipeline Dashboard back-link | base.html, pipeline_dashboard.html |
| 8 | Allow team_lead access to batch reports (picker, briefing view, PDF) | analytics.py |
| 9 | Remove Home back-link from inspector_audit | inspector_audit.html |

## 3. CRITICAL CHANGE: PLAYWRIGHT RUNNING HEADER

Previously v245 deferred page 7 overflow fix (options A/B/C/D). Went with **A — Playwright headerTemplate**. Implementation:

- `app/services/pdf_playwright.py` — `html_to_pdf()` now accepts `header_template` and `margin` params; backward compatible.
- `app/routes/analytics.py` `batch_briefing_pdf` — builds a header with `<span class="pageNumber">` / `<span class="totalPages">` placeholders; passes `top: 22mm` margin so header doesn't clip.
- `briefing.html` `@media print` — hides `.page-meta` so on-screen labels don't duplicate with Playwright's running header.

Result: every physical page in the PDF has `SR-XXX · [date] · Power Park Student Housing Phase 3 · Page X of Y`. Overflow pages no longer orphaned. Works for both SR-013 (tight) and SR-012 (long).

## 4. CURRENT STATE

- HEAD at latest nav/access commits, working tree clean
- Batch Reports reachable by team_lead, manager, admin from desktop + mobile nav
- Home link visible only to inspector/office_admin
- Analytics dashboard kept as route (accessible by URL, not in nav)
- Briefing PDF generation verified on SR-013 and SR-012

## 5. OUTSTANDING FROM THIS SESSION

**Pipeline snapshot vs live reconciliation (IN PROGRESS, context ran out).**

User asked: "diff between snapshot (13 April) and live = reviewed-or-higher units in SR-013 — correct? show open-defect recon."

Verified so far:
- Snapshot cutoff: `2026-04-12 22:00:00` UTC
- Filter is `inspection.submitted_at <= cutoff` AND `status IN ('reviewed','approved','pending_followup')` — NOT a batch filter
- Last inspection in snapshot: 10 Apr 16:52 — SR-012 unit 051
- Distinct batches contributing: SR-012 (28 insp), SR-011 (20), SR-010 (8), SR-009 (1)

**Still pending:** Run the reconciliation query in new session. User wants snapshot open defects, live open defects, and a decomposition of the diff (new defects raised after snapshot / cleared after snapshot / newly visible via review after snapshot). Draft query is in the v245 chat transcript. Too long for one Render paste — break into 3 separate heredoc queries.

**Hypothesis to test:** if user's claim holds, the diff should be exactly SR-013 inspection activity. But user's claim assumed batch filtering; actual filter is submission timestamp. Likely diff includes any inspection submitted between 12 Apr 22:00 UTC and now — not strictly SR-013.

## 6. OUTSTANDING (CARRIED FROM v245)

- **SR-014 inspector setup** — still blocking inspections. Higher priority than briefing refinements.
- **Old route cleanup** — `batch_report_view`, `batch_report_pdf`, `_build_batch_report_data()`, `report_batch.html`. User greenlights when ready.
- **Analytics Tier 1** — cycle comparison / rectification scorecard (when more C2 data flows)
- Data-quality cleanup of exclusion list 69ce0e91 duplicates

## 7. RULES FOR NEXT CLAUDE (v246 additions)

**116. Answer with code, not cadence inference.** When asked "last batch in the snapshot", I guessed by closure date ("SR-011"). Wrong. The actual filter was `inspection.submitted_at`. Always read the query predicate before answering any "what's included" question.

**117. Break long Render queries into small heredocs.** User flagged "tl for render" after a 60-line Python heredoc. Ceiling is ~40 lines per paste. Split reconciliation queries into 3 sequential blocks: (a) open-defect counts, (b) new-defect decomposition, (c) cleared-defect decomposition.

**118. Decorator consistency after nav changes.** When widening nav access to a role, always check all three decorator levels used by that feature's routes. Missed `@require_admin` on the picker and `@require_manager` on the briefing routes in the same session — had to chase a 403 after the fact.

**119. `require_team_lead` allows team_lead + manager + admin. `require_manager` allows manager + admin. `require_admin` allows admin only.** Documented in `app/auth.py` 165–210. Use the lowest privilege that matches the nav gate.

**120. `.page-meta` is now display:none in print.** Any future tweaks to per-page headers in the briefing PDF should modify `header_template` in `batch_briefing_pdf` (analytics.py line ~4713), NOT the in-template `.page-meta` divs.

## 8. KEY IDs & CONSTANTS

- Snapshot cycle anchor: `_CYCLE_END_ANCHOR = Mon 13 April 2026` → UTC cutoff `2026-04-12 22:00:00`
- Briefing PDF margin (with header): `top 22mm / bottom 20mm / left 16mm / right 16mm`
- Pipeline dashboard filter: `inspection.submitted_at <= snapshot_str` with status gate
- Everything else from v245 §7 still valid

## 9. STARTING PROTOCOL FOR NEXT SESSION

1. Read this handover end-to-end
2. Confirm git state: `git log --oneline | head -12`
3. Ask user: "Pick up pipeline snapshot/live reconciliation, SR-014 setup, old route cleanup, or something else?"
4. If reconciliation: start with the 3-part heredoc strategy (§5 above)

**END OF HANDOVER v246**
