#!/usr/bin/env python3
"""
fix_detail_list_bfwd.py
Bug: batch detail list (/batches/<id>) shows "X of Y B/fwd cleared" where
     Y = defect_bfwd (every prior-cycle defect, ANY status). Unit 027 C3
     shows "2 of 35" when only 2 are actionable this cycle.
Fix: denominator + green-check use defect_bfwd_action (open OR cleared-this-
     cycle) -- already computed in the detail builder (batches.py L407) and
     attached to the unit (L413). Unit 027 -> "2 of 2 B/fwd cleared".
     Single-line, two occurrences, template only.

RUN ON: MACBOOK
"""
import io

PATH = "app/templates/batches/_detail_tbody.html"

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

old = ('                <span class="font-medium {% if u.defect_bfwd and '
       'u.defect_cleared >= u.defect_bfwd %}text-green-600{% endif %}">'
       '{{ u.defect_cleared }}</span> of {{ u.defect_bfwd }} B/fwd cleared')
new = ('                <span class="font-medium {% if u.defect_bfwd_action and '
       'u.defect_cleared >= u.defect_bfwd_action %}text-green-600{% endif %}">'
       '{{ u.defect_cleared }}</span> of {{ u.defect_bfwd_action }} B/fwd cleared')

assert src.count(old) == 1, "anchor not unique/found: %d" % src.count(old)
src = src.replace(old, new)

# guard: no stray defect_bfwd (non-action) left in this template
assert "u.defect_bfwd " not in src and "u.defect_bfwd %}" not in src and \
       "u.defect_bfwd }}" not in src, "residual non-action defect_bfwd remains"

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("OK: detail-list b/fwd denominator -> defect_bfwd_action (2 occurrences on L49).")
