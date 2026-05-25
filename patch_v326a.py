"""
v326a — desnag still_open count fix
Three changes in app/routes/inspection.py:
  1. defect_still_open (L~2504) — count all open priors, not just addressed-this-cycle
  2. _desnag_progress SQL still_open SUM — same fix in SQL form
  3. _desnag_progress params — remove one cycle_number now that still_open SUM uses one less placeholder
Result: header pill on /inspection/<id>/desnag and HTMX progress updates both show
        5 still open (3 actioned + 2 unactioned) instead of 3.
Latent symmetry (latent_still_open) deferred to v326-latents follow-up.
"""
import pathlib

P = pathlib.Path('app/routes/inspection.py')
src = P.read_text()

# ---- FIX 1 ----
old1 = "    defect_still_open = sum(1 for d in bfwd_open if d['addressed_cycle_number'] == cycle_number)\n"
new1 = "    defect_still_open = len(bfwd_open)  # v326a: all open priors (actioned + unactioned)\n"
assert old1 in src, "FIX 1 match failed"
assert src.count(old1) == 1, "FIX 1 not unique"
src = src.replace(old1, new1)

# ---- FIX 2 ----
old2 = "            SUM(CASE WHEN status = 'open' AND addressed_cycle_number = ? THEN 1 ELSE 0 END) as still_open\n"
new2 = "            SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as still_open\n"
assert old2 in src, "FIX 2 match failed"
assert src.count(old2) == 1, "FIX 2 not unique"
src = src.replace(old2, new2)

# ---- FIX 3 ----
old3 = '    """, [cycle_number, cycle_number, cycle_number, unit_id, tenant_id, cycle_number, cycle_number], one=True)\n'
new3 = '    """, [cycle_number, cycle_number, unit_id, tenant_id, cycle_number, cycle_number], one=True)\n'
assert old3 in src, "FIX 3 match failed"
assert src.count(old3) == 1, "FIX 3 not unique"
src = src.replace(old3, new3)

P.write_text(src)
print("v326a applied: 3 fixes to app/routes/inspection.py")
