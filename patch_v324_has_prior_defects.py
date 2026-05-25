#!/usr/bin/env python3
"""v324: Complete the duplicate defect render fix (v323 was incomplete).

ROOT CAUSE
----------
v323 suppressed items-section render when `has_open_prior=True`. But
`_single_item.html` L23 gates its `show_prior` block on
`has_prior_defects` (ANY priors — open or cleared), not `has_open_prior`.

After an inspector taps "Cleared" on a defect in the categories loop,
the defect's status becomes 'cleared', `has_open_prior` becomes False,
and v323 no longer suppresses the item. The items section then renders
it, `show_prior` fires, and L76 loops through the cleared prior with a
Clear/Undo button. Meanwhile the categories loop renders the same defect
with "Cleared + Undo" controls. Different endpoints, conflicting stale
state on HTMX swap.

FIX
---
Widen the items-section suppression to match `show_prior`'s gate:
suppress when `has_prior_defects=True` regardless of whether priors are
open or cleared. Mirror v323's parent-aware exemption with a parallel
`parent_has_prior_defects_map` so children of newly-suppressed parents
remain visible.

THREE COORDINATED EDITS
-----------------------
1. inspection.py: add `parent_has_prior_defects_map` next to existing
   `parent_has_open_prior_map`.
2. inspection.py: surface `parent_has_prior_defects` on child checklist
   items (alongside existing `parent_has_open_prior`).
3. _desnag_items.html L19 + L20: widen the outer suppression guard from
   `has_open_prior` to `has_prior_defects`, and the parent exemption
   from `parent_has_open_prior` to `parent_has_prior_defects`.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY_FILE = ROOT / "app" / "routes" / "inspection.py"
TPL_FILE = ROOT / "app" / "templates" / "inspection" / "_desnag_items.html"


# -- EDIT 1: inspection.py -- add parent_has_prior_defects_map -------------
old_1 = """            # v323: per-parent has_open_prior so newly-visible children whose
            # parent is suppressed from the items section still render unhidden.
            parent_has_open_prior_map = {
                tid: any(d['status'] == 'open' for d in prior_defects_map.get(tid, []))
                for tid in parent_items
            }

            checklist = []
"""

new_1 = """            # v323: per-parent has_open_prior so newly-visible children whose
            # parent is suppressed from the items section still render unhidden.
            parent_has_open_prior_map = {
                tid: any(d['status'] == 'open' for d in prior_defects_map.get(tid, []))
                for tid in parent_items
            }
            # v324: per-parent has_prior_defects (any priors, open or cleared).
            # Mirror of parent_has_open_prior_map but broader — gates child
            # visibility when parent is suppressed for having ANY priors.
            parent_has_prior_defects_map = {
                tid: len(prior_defects_map.get(tid, [])) > 0
                for tid in parent_items
            }

            checklist = []
"""


# -- EDIT 2: inspection.py -- surface parent_has_prior_defects -------------
old_2 = """                    'parent_has_open_prior': parent_has_open_prior_map.get(i['parent_item_id'], False) if is_child else False,
"""

new_2 = """                    'parent_has_open_prior': parent_has_open_prior_map.get(i['parent_item_id'], False) if is_child else False,
                    'parent_has_prior_defects': parent_has_prior_defects_map.get(i['parent_item_id'], False) if is_child else False,
"""


# -- EDIT 3: _desnag_items.html -- widen suppression guard ---------------
old_3 = """        {% if item.status != 'skipped' and (not item.is_carried_ok|default(false) or item.children_have_defects|default(false)) and not item.has_open_prior|default(false) %}
        <div id="item-{{ item.id }}"{% if item.parent_item_id %} data-parent-id="{{ item.parent_item_id }}"{% endif %}{% if item.parent_item_id and item.parent_status in [none, "pending"] and not (is_followup and item.has_open_prior|default(false)) and not (is_followup and item.parent_has_open_prior|default(false)) %} style="display:none"{% endif %}>"""

new_3 = """        {% if item.status != 'skipped' and (not item.is_carried_ok|default(false) or item.children_have_defects|default(false)) and not item.has_prior_defects|default(false) %}
        <div id="item-{{ item.id }}"{% if item.parent_item_id %} data-parent-id="{{ item.parent_item_id }}"{% endif %}{% if item.parent_item_id and item.parent_status in [none, "pending"] and not (is_followup and item.has_open_prior|default(false)) and not (is_followup and item.parent_has_prior_defects|default(false)) %} style="display:none"{% endif %}>"""


# -- APPLY -----------------------------------------------------------------
def patch(path, old, new, label):
    content = path.read_text()
    assert old in content, f"MATCH FAILED: {label}"
    occurrences = content.count(old)
    assert occurrences == 1, f"AMBIGUOUS MATCH ({occurrences}x): {label}"
    path.write_text(content.replace(old, new))
    print(f"  OK  {label}")


print("v324 patch -- complete duplicate defect render fix")
print()
print(f"File: {PY_FILE.relative_to(ROOT)}")
patch(PY_FILE, old_1, new_1, "inspection.py: parent_has_prior_defects_map")
patch(PY_FILE, old_2, new_2, "inspection.py: parent_has_prior_defects on checklist")
print()
print(f"File: {TPL_FILE.relative_to(ROOT)}")
patch(TPL_FILE, old_3, new_3, "_desnag_items.html: widen suppression to has_prior_defects")
print()
print("All edits applied. Next:")
print("  git diff --stat")
print("  git diff app/routes/inspection.py app/templates/inspection/_desnag_items.html")
