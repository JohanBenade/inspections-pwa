import sqlite3
from collections import defaultdict
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TID = 'MONOGRAPH'

# C2 units among the 69 (by unit_number)
C2_UNITS = ["248","250","014","015","016","023","227","230","231","233",
            "237","239","241","243","042","045","049","050","051","052",
            "148","252","053","055","056","057","269"]
print("C2 units in 69:", len(C2_UNITS))

groups = defaultdict(list)   # exclusion_list_id -> [unit_number...]
missing = []
for un in C2_UNITS:
    u = c.execute("SELECT id FROM unit WHERE tenant_id=? AND unit_number=?", [TID, un]).fetchone()
    if not u:
        missing.append((un, "no unit row")); continue
    insp = c.execute("""SELECT exclusion_list_id FROM inspection
        WHERE unit_id=? AND tenant_id=? AND cycle_number=2
        ORDER BY created_at DESC LIMIT 1""", [u['id'], TID]).fetchone()
    if not insp:
        missing.append((un, "no C2 inspection")); continue
    groups[insp['exclusion_list_id']].append(un)

print("\nDistinct exclusion lists applied to C2 units:", len(groups))
for elid, units in groups.items():
    if elid is None:
        print(f"\n  list_id = NULL  (no exclusion list)  -> {len(units)} units")
    else:
        el = c.execute("SELECT name, item_count FROM exclusion_list WHERE id=?", [elid]).fetchone()
        live = c.execute("SELECT COUNT(*) n FROM exclusion_list_item WHERE exclusion_list_id=?", [elid]).fetchone()['n']
        nm = el['name'] if el else "(list row missing)"
        stored = el['item_count'] if el else "?"
        print(f"\n  list_id = {elid}")
        print(f"    name        : {nm}")
        print(f"    item_count  : stored={stored}  live_rows={live}")
        print(f"    units ({len(units)}): {', '.join(sorted(units))}")

if missing:
    print("\nUNRESOLVED:", missing)
