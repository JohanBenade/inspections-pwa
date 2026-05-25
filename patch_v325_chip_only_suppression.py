#!/usr/bin/env python3
"""v325: Correct duplicate defect render fix.

WHY v323 AND v324 WERE WRONG
----------------------------
Both suppressed the ENTIRE item from items section when priors existed
(v323: has_open_prior; v324: has_prior_defects). This breaks the
workflow: every item must be MS/NTS-marked by the inspector (nothing
auto-updates from prior-clearing actions). Suppressing the item hides
its MS/NTS controls, so items with priors can never reach addressed
state.

CORRECT FIX
-----------
The duplicate render is the prior-defect chip block inside
_single_item.html (L74, `{% if show_prior %}`), not the item itself.
Suppress JUST the chip block when included from _desnag_items.html;
keep the rest of the item rendering intact.

THREE COORDINATED EDITS
-----------------------
1. _desnag_items.html L19+L20: revert to pre-v323 state (item renders
   again, with full MS/NTS controls).
2. _desnag_items.html before the include: set hide_prior_chips=true.
3. _single_item.html L23: gate show_prior on not hide_prior_chips.

Result: item renders normally with MS/NTS available. Prior-defect
chips suppressed only in desnag context (they're rendered by the
categories loop instead). No duplicate, workflow preserved.

NOTE: leaves parent_has_open_prior_map and parent_has_prior_defects_map
intact in inspection.py — unused dead code now, but harmless. Clean up
as part of repo hygiene later.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
ITEMS = ROOT / "app" / "templates" / "inspection" / "_desnag_items.html"
SINGLE = ROOT / "app" / "templates" / "inspection" / "_single_item.html"


# -- EDIT 1: _desnag_items.html -- revert L19/L20, add hide_prior_chips ----
old_1 = """        {% if item.status != 'skipped' and (not item.is_carried_ok|default(false) or item.children_have_defects|default(false)) and not item.has_prior_defects|default(false) %}
        <div id="item-{{ item.id }}"{% if item.parent_item_id %} data-parent-id="{{ item.parent_item_id }}"{% endif %}{% if item.parent_item_id and item.parent_status in [none, "pending"] and not (is_followup and item.has_open_prior|default(false)) and not (is_followup and item.parent_has_prior_defects|default(false)) %} style="display:none"{% endif %}>
        {% include 'inspection/_single_item.html' %}"""

new_1 = """        {% if item.status != 'skipped' and (not item.is_carried_ok|default(false) or item.children_have_defects|default(false)) %}
        <div id="item-{{ item.id }}"{% if item.parent_item_id %} data-parent-id="{{ item.parent_item_id }}"{% endif %}{% if item.parent_item_id and item.parent_status in [none, "pending"] and not (is_followup and item.has_open_prior|default(false)) %} style="display:none"{% endif %}>
        {% set hide_prior_chips = true %}
        {% include 'inspection/_single_item.html' %}"""


# -- EDIT 2: _single_item.html -- gate show_prior on hide_prior_chips -----
old_2 = """{% set show_prior = is_followup and has_prior %}"""

new_2 = """{% set show_prior = is_followup and has_prior and not hide_prior_chips|default(false) %}"""


# -- APPLY -----------------------------------------------------------------
def patch(path, old, new, label):
    content = path.read_text()
    assert old in content, f"MATCH FAILED: {label}"
    occurrences = content.count(old)
    assert occurrences == 1, f"AMBIGUOUS MATCH ({occurrences}x): {label}"
    path.write_text(content.replace(old, new))
    print(f"  OK  {label}")


print("v325 patch -- correct duplicate render fix without over-suppression")
print()
print(f"File: {ITEMS.relative_to(ROOT)}")
patch(ITEMS, old_1, new_1, "_desnag_items.html: revert L19/L20, add hide_prior_chips")
print()
print(f"File: {SINGLE.relative_to(ROOT)}")
patch(SINGLE, old_2, new_2, "_single_item.html: gate show_prior on hide_prior_chips")
print()
print("All edits applied. Next:")
print("  git diff --stat")
print("  git diff app/templates/inspection/")
