#!/usr/bin/env python3
"""
fix_live_card_bfwd.py
Bug: /live card shows bfwd = every prior-cycle defect (ANY status).
     Unit 027 C3 shows 35 b/fwd when only 2 are open.
Fix: feed the card from bfwd_action (open OR cleared-this-cycle), which the
     builder already computes correctly. Two source swaps in
     _build_live_monitor_data. No template change.

RUN ON: MACBOOK
"""
import io

PATH = "app/routes/batches.py"

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# --- Change 1: unit hero source (L1869) ---
old1 = "        u['bfwd_defects'] = bfwd_map.get(u['unit_id'], 0)"
new1 = "        u['bfwd_defects'] = bfwd_action_map.get(u['unit_id'], 0)"
assert src.count(old1) == 1, "Change 1 anchor not unique/found: %d" % src.count(old1)
src = src.replace(old1, new1)

# --- Change 2: area-level source (L1900) ---
old2 = "                    'bfwd': bfwd_area_map.get((uid, aname), 0),"
new2 = "                    'bfwd': bfwd_action_area_map.get((uid, aname), 0),"
assert src.count(old2) == 1, "Change 2 anchor not unique/found: %d" % src.count(old2)
src = src.replace(old2, new2)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("OK: both swaps applied.")
print(" L1869 bfwd_map        -> bfwd_action_map")
print(" L1900 bfwd_area_map   -> bfwd_action_area_map")
