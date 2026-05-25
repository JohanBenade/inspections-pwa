#!/usr/bin/env python3
"""v323: Fix duplicate defect render on C2 de-snag screen.

ROOT CAUSE
----------
The "Items to inspect" section in desnag.html includes _desnag_items.html ->
_single_item.html, which renders prior_defects + a "Defects Remain" item-level
button for any inspection_item that has open prior defects. The SAME defects
are also rendered above by the categories loop via _desnag_defect.html, with
green/red "Cleared / Still Open" buttons targeting #defect-{id}.

After an HTMX swap on one path, the other stays stale -> inspectors see
conflicting controls for the same defect.

The grand-totals counter at L2429 already documents intent: the items cohort
is "newly-visible at C2+, has_prior_defects=0". The renderer drifted from
that intent and pulls in items with prior defects too.

THREE COORDINATED EDITS
-----------------------
1. inspection.py — compute parent_has_open_prior_map once per category
   loop, surface parent_has_open_prior on each child checklist entry.
2. _desnag_items.html — suppress items with has_open_prior=True from the
   items section (they're rendered canonically in the categories loop).
3. _desnag_items.html — keep newly-visible children unhidden when their
   parent is suppressed (parent_has_open_prior=True).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY_FILE = ROOT / "app" / "routes" / "inspection.py"
TPL_FILE = ROOT / "app" / "templates" / "inspection" / "_desnag_items.html"


# -- EDIT 1: inspection.py -- add parent_has_open_prior_map computation -----
old_1 = """            # Which parents have pending children (drives children_have_defects flag)
            parent_has_pending_child = set()
            for i in cat_items:
                if i['status'] == 'pending' and i['parent_item_id']:
                    parent_has_pending_child.add(i['parent_item_id'])

            checklist = []
"""

new_1 = """            # Which parents have pending children (drives children_have_defects flag)
            parent_has_pending_child = set()
            for i in cat_items:
                if i['status'] == 'pending' and i['parent_item_id']:
                    parent_has_pending_child.add(i['parent_item_id'])

            # v323: per-parent has_open_prior so newly-visible children whose
            # parent is suppressed from the items section still render unhidden.
            parent_has_open_prior_map = {
                tid: any(d['status'] == 'open' for d in prior_defects_map.get(tid, []))
                for tid in parent_items
            }

            checklist = []
"""


# -- EDIT 2: inspection.py -- surface parent_has_open_prior on checklist ----
old_2 = """                    'children_have_defects': (i['template_id'] in parent_has_pending_child) if is_parent else False,
                    'inspection_defects': inspection_defects_map.get(i['id'], []),"""

new_2 = """                    'children_have_defects': (i['template_id'] in parent_has_pending_child) if is_parent else False,
                    'parent_has_open_prior': parent_has_open_prior_map.get(i['parent_item_id'], False) if is_child else False,
                    'inspection_defects': inspection_defects_map.get(i['id'], []),"""


# -- EDIT 3: _desnag_items.html -- filter items + child visibility ---------
old_3 = """        {% if item.status != 'skipped' and (not item.is_carried_ok|default(false) or item.children_have_defects|default(false)) %}
        <div id="item-{{ item.id }}"{% if item.parent_item_id %} data-parent-id="{{ item.parent_item_id }}"{% endif %}{% if item.parent_item_id and item.parent_status in [none, "pending"] and not (is_followup and item.has_open_prior|default(false)) %} style="display:none"{% endif %}>"""

new_3 = """        {% if item.status != 'skipped' and (not item.is_carried_ok|default(false) or item.children_have_defects|default(false)) and not item.has_open_prior|default(false) %}
        <div id="item-{{ item.id }}"{% if item.parent_item_id %} data-parent-id="{{ item.parent_item_id }}"{% endif %}{% if item.parent_item_id and item.parent_status in [none, "pending"] and not (is_followup and item.has_open_prior|default(false)) and not (is_followup and item.parent_has_open_prior|default(false)) %} style="display:none"{% endif %}>"""


# -- APPLY -----------------------------------------------------------------
def patch(path, old, new, label):
    content = path.read_text()
    assert old in content, f"MATCH FAILED: {label}"
    occurrences = content.count(old)
    assert occurrences == 1, f"AMBIGUOUS MATCH ({occurrences}x): {label}"
    path.write_text(content.replace(old, new))
    print(f"  OK  {label}")


print("v323 patch -- duplicate defect render fix")
print()
print(f"File: {PY_FILE.relative_to(ROOT)}")
patch(PY_FILE, old_1, new_1, "inspection.py: parent_has_open_prior_map computation")
patch(PY_FILE, old_2, new_2, "inspection.py: parent_has_open_prior on checklist")
print()
print(f"File: {TPL_FILE.relative_to(ROOT)}")
patch(TPL_FILE, old_3, new_3, "_desnag_items.html: filter + child visibility")
print()
print("All edits applied. Next:")
print("  git diff --stat")
print("  git diff app/routes/inspection.py app/templates/inspection/_desnag_items.html")
