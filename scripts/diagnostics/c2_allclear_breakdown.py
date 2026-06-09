import sqlite3
from collections import defaultdict
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TID = 'MONOGRAPH'

C2_UNITS = ["248","250","014","015","016","023","227","230","231","233",
            "237","239","241","243","042","045","049","050","051","052",
            "148","252","053","055","056","057","269"]

# confirm the universe of statuses present on these C2 inspections
print("=== distinct statuses across these C2 inspections ===")
allst = set()
recs = {}
for un in C2_UNITS:
    u = c.execute("SELECT id, floor FROM unit WHERE tenant_id=? AND unit_number=?", [TID, un]).fetchone()
    insp = c.execute("""SELECT id FROM inspection WHERE unit_id=? AND tenant_id=? AND cycle_number=2
        ORDER BY created_at DESC LIMIT 1""", [u['id'], TID]).fetchone()
    rows = c.execute("SELECT status, COUNT(*) n FROM inspection_item WHERE inspection_id=? GROUP BY status", [insp['id']]).fetchall()
    bd = {r['status']: r['n'] for r in rows}
    allst |= set(bd.keys())
    total = sum(bd.values())
    recs[un] = (u['floor'], total, bd)
print(sorted(allst))

print("\n=== per-unit breakdown (sorted by floor, unit) ===")
print("UNIT | FL | TOTAL | ok | NTS | NI | pending | skipped | ALL_CLEAR")
order = sorted(C2_UNITS, key=lambda x: (recs[x][0], x))
gf_all_clear = above_all_clear = 0
gf_units = above_units = 0
for un in order:
    fl, total, bd = recs[un]
    ok = bd.get('ok',0); nts = bd.get('not_to_standard',0); ni = bd.get('not_installed',0)
    pend = bd.get('pending',0); sk = bd.get('skipped',0)
    all_clear = (pend==0 and sk==0 and nts==0 and ni==0 and ok==total)
    print(f"{un}  | {fl}  | {total} | {ok} | {nts} | {ni} | {pend} | {sk} | {'YES' if all_clear else 'no'}")
    if fl == 0:
        gf_units += 1; gf_all_clear += 1 if all_clear else 0
    else:
        above_units += 1; above_all_clear += 1 if all_clear else 0

print("\n=== GF vs above-GF summary ===")
print(f"GF (floor 0):     {gf_units} units, {gf_all_clear} fully all-clear (every item ok, 0 skipped)")
print(f"Above GF (1/2):   {above_units} units, {above_all_clear} fully all-clear")
# item-total ranges by tier
gf_tot = sorted(set(recs[u][1] for u in order if recs[u][0]==0))
ab_tot = sorted(set(recs[u][1] for u in order if recs[u][0]!=0))
print(f"GF item totals seen: {gf_tot}")
print(f"Above-GF item totals seen: {ab_tot}")
