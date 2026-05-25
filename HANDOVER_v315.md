# Handover v315 — 24 May 2026
HEAD: v325 deployed (build patch_v325_chip_only_suppression.py). 
Previous: v324 `2303721`, v323 `301d75e`, v322 `6812baa`.

## What shipped this thread
- **v324** (commit `2303721`) — ATTEMPTED widening of items-section suppression from has_open_prior to has_prior_defects. WRONG fix. Broke the workflow: inspector lost MS/NTS access for items with priors.
- **v325** (build script ready, awaiting smoke test) — CORRECT fix. Reverts v323+v324 item-level suppression in `_desnag_items.html` L19/L20. Adds `hide_prior_chips=true` before include. Adds `not hide_prior_chips` gate to `show_prior` in `_single_item.html` L23. Result: items render with full MS/NTS, prior chips only suppressed in desnag context (categories loop owns prior actions).

## CRITICAL workflow rule learned this thread
**Per Johan: "the inspector must mark every item to be marked. nothing gets auto-updated."**
- Clearing a prior defect via Clear/Still-Open does NOT update inspection_item.status.
- Inspector must additionally click MS/NTS on each item with priors.
- inspection_item.status='pending' for items with cleared priors is CORRECT, not a bug.
- Parent INST + child NTS is VALID — parent is structurally present, child reports defect on a sub-feature.

## Unit 011 (insp 1f666236) state at handover
- 508 inspection_items: 24 NTS, 474 ok, 10 pending
- 38 priors (33 cleared @ C2 + 5 open: 3 actioned-still-open, 2 unactioned)
- 2 unactioned priors: CEILING/plaster recess "Two town near bathroom door", BEDROOM B/W3 operation "Hard to close at bottom window"
- 10 pending all have has_prior_defects=1. 2 of them = the unactioned priors. 8 of them = priors cleared at C2 but item not yet MS/NTS-marked.
- Header reports 123/125 addressed = 2 pending (the 2 unactioned priors). Header denominator counts priors+items differently from raw inspection_item.status='pending'.
- C1 marks confirmed for all 10 items (queried 24 May): all `not_to_standard` with marked_at 2026-03-13 13:02-13:52.

## v325 pending tasks
1. Push v325 (Johan still needs to `git push` after running the patch)
2. Smoke test on unit 011: hard refresh, verify (a) defects appear once (in categories area), (b) 8 phantom-pending items show MS/NTS controls in items section, (c) MS-marking one of them moves it out of pending.
3. If smoke passes, also verify on unit 012 (insp f09ce571).
4. If smoke fails, paste what's seen and triage.

## Header label backlog (low priority)
Header pill shows "3 still open" but actual open priors = 5 (3 actioned-still-open + 2 unactioned). Inspector reading just the pill misses the 2 unactioned. Consider relabel to "5 still open" or split.

## v324 cleanup backlog
v324 added `parent_has_prior_defects_map` + checklist field in inspection.py around L2386-L2421. v325 doesn't reference them anymore. Dead code, harmless. Remove in next cleanup pass.

## Carried over from v314
- v322 SMB Page 1 smoke test still not done
- v319 follow-up: 4 surfaces certified-unit audit
- v309 BUGS #2/#3 verification (different bug, not the v325 one)
- v275/v276/v277 SMB enrichments
- Repo hygiene: ~26 untracked patch_*.py files
- Memory #12 correction: SMB function is `_build_pipeline_report_data` at L5500, template `site_meeting_brief.html`

## Memory rules reinforced this thread
- Rule #20 (NEVER ASSUME): caught me on defect schema (joins via unit_id+item_template_id, not inspection_item_id directly) and on the workflow (must MS/NTS every item).
- Rule #16 (language): English, no deliberation.
- Inspector marks every item; nothing auto-updates (NEW RULE — add to memory).
