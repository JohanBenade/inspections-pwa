"""
c2_cohort_27.py — de-snag cohort (checkpoints) for the 27 C2 units in the 69.

Inherits project() + all global preloads VERBATIM from sr017_projection_v2.py
(the validated master; anchors unit 046=24, unit 146=198).
ONLY the iteration source changes: live-derived 27 C2 units instead of one batch.

KEY: excl_list_id is sourced from inspection.exclusion_list_id (what ACTUALLY
applied), not batch_unit.exclusion_list_id — the 7 NULL-link units had the list
on batch_unit but never copied to the inspection, so the fuller item set applied.
"""
import sqlite3
from datetime import datetime as dt, timedelta as td

TENANT_ID = 'MONOGRAPH'
conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ==========================================================================
# GLOBAL PRELOADS  (verbatim from sr017_projection_v2.py)
# ==========================================================================
cycle_meta = {}
for r in cur.execute("SELECT id, cycle_number, block, floor FROM inspection_cycle WHERE tenant_id=?",
                     (TENANT_ID,)).fetchall():
    cycle_meta[r['id']] = dict(r)

all_templates = {}
for r in cur.execute("SELECT id, parent_item_id, floor_condition, active FROM item_template WHERE tenant_id=?",
                     (TENANT_ID,)).fetchall():
    all_templates[r['id']] = dict(r)

parent_to_children = {}
for tid, t in all_templates.items():
    pid = t['parent_item_id']
    if pid:
        parent_to_children.setdefault(pid, []).append(tid)
parents_with_kids = set(parent_to_children.keys())

prev_items_by_unit_cycle = {}
for r in cur.execute("""
    SELECT i.unit_id, i.cycle_number, ii.item_template_id, ii.status
    FROM inspection_item ii JOIN inspection i ON ii.inspection_id = i.id
    WHERE i.tenant_id = ?""", (TENANT_ID,)).fetchall():
    prev_items_by_unit_cycle.setdefault((r['unit_id'], r['cycle_number']), {})[r['item_template_id']] = r['status']

defects_by_unit = {}
for r in cur.execute("""
    SELECT unit_id, item_template_id, raised_cycle_id, raised_cycle_number, status, cleared_cycle_number
    FROM defect WHERE tenant_id = ?""", (TENANT_ID,)).fetchall():
    defects_by_unit.setdefault(r['unit_id'], []).append(dict(r))

latents_by_unit = {}
for r in cur.execute("""
    SELECT unit_id, rectified_at, rectified_at_cycle_number
    FROM latent_area_note WHERE tenant_id = ?""", (TENANT_ID,)).fetchall():
    latents_by_unit.setdefault(r['unit_id'], []).append(dict(r))

excl_by_list = {}
for r in cur.execute("SELECT exclusion_list_id, item_template_id FROM exclusion_list_item").fetchall():
    excl_by_list.setdefault(r['exclusion_list_id'], set()).add(r['item_template_id'])

excl_by_cycle = {}
for r in cur.execute("SELECT cycle_id, item_template_id FROM cycle_excluded_item WHERE tenant_id=?",
                     (TENANT_ID,)).fetchall():
    excl_by_cycle.setdefault(r['cycle_id'], set()).add(r['item_template_id'])

# ==========================================================================
# PER-UNIT PROJECTION  (verbatim from sr017_projection_v2.py)
# ==========================================================================
def project(unit_id, cycle_id, excl_list_id, unit_floor, cycle_number):
    if excl_list_id and excl_list_id in excl_by_list:
        current_exclusions = excl_by_list[excl_list_id]
    elif cycle_id and cycle_id in excl_by_cycle:
        current_exclusions = excl_by_cycle[cycle_id]
    else:
        current_exclusions = set()

    prev_item_map = {}
    if cycle_number > 1:
        prev_item_map = prev_items_by_unit_cycle.get((unit_id, cycle_number - 1), {})

    prior_defect_set = set()
    for d in defects_by_unit.get(unit_id, []):
        if d['status'] == 'open' and d['raised_cycle_id'] != cycle_id:
            prior_defect_set.add(d['item_template_id'])

    c2_status = {}
    hpd = {}
    for tid, t in all_templates.items():
        if t['active'] != 1:
            continue
        if tid in current_exclusions:
            s = 'skipped'
        elif t['floor_condition'] == 'ground_only' and unit_floor > 0:
            s = 'skipped'
        elif cycle_number > 1 and prev_item_map:
            prev_s = prev_item_map.get(tid)
            if not prev_s or prev_s == 'pending':
                s = 'ok'
            elif prev_s == 'ok':
                s = 'ok'
            elif prev_s in ('not_to_standard', 'not_installed'):
                s = 'pending'
            elif prev_s == 'skipped':
                s = 'pending'
            else:
                s = 'pending'
        else:
            prev_s = prev_item_map.get(tid)
            s = prev_s if prev_s else 'pending'
        c2_status[tid] = s
        hpd[tid] = 1 if tid in prior_defect_set else 0

    if cycle_number > 1:
        for tid in list(c2_status.keys()):
            t = all_templates[tid]
            if t['parent_item_id'] is not None: continue
            if tid not in parents_with_kids: continue
            if c2_status[tid] != 'pending' or hpd[tid] != 0: continue
            kids = [ch for ch in parent_to_children.get(tid, []) if ch in c2_status]
            if all(c2_status[ch] == 'skipped' for ch in kids):
                c2_status[tid] = 'ok'
        for tid in list(c2_status.keys()):
            t = all_templates[tid]
            if t['parent_item_id'] is None: continue
            if c2_status[tid] != 'pending' or hpd[tid] != 0: continue
            pid = t['parent_item_id']
            pt = all_templates.get(pid)
            if not pt or pt['parent_item_id'] is not None: continue
            if c2_status.get(pid) == 'pending' and hpd.get(pid, 0) == 0:
                c2_status[tid] = 'ok'
        for tid in list(c2_status.keys()):
            t = all_templates[tid]
            if t['parent_item_id'] is not None: continue
            if tid not in parents_with_kids: continue
            if c2_status[tid] != 'pending' or hpd[tid] != 0: continue
            c2_status[tid] = 'ok'

    items = sum(1 for tid, s in c2_status.items() if s == 'pending' and hpd[tid] == 0)

    d_count = 0
    for d in defects_by_unit.get(unit_id, []):
        if d['raised_cycle_number'] is None or d['raised_cycle_number'] >= cycle_number:
            continue
        if d['status'] == 'open':
            d_count += 1
        elif d['status'] == 'cleared' and d['cleared_cycle_number'] == cycle_number:
            d_count += 1

    l_count = 0
    for l in latents_by_unit.get(unit_id, []):
        if l['rectified_at'] is None:
            l_count += 1
        elif l['rectified_at_cycle_number'] == cycle_number:
            l_count += 1

    return d_count, l_count, items

# ==========================================================================
# ANCHOR VALIDATION (per EASY_TARGETS_SOP — must pass before trusting output)
# ==========================================================================
def run_unit(unit_number):
    u = cur.execute("SELECT id, floor FROM unit WHERE tenant_id=? AND unit_number=?",
                    (TENANT_ID, unit_number)).fetchone()
    if not u: return None
    # latest inspection for the unit (its current cycle)
    insp = cur.execute("""SELECT cycle_id, cycle_number, exclusion_list_id FROM inspection
        WHERE unit_id=? AND tenant_id=? ORDER BY cycle_number DESC, created_at DESC LIMIT 1""",
        (u['id'], TENANT_ID)).fetchone()
    if not insp: return None
    try: floor = int(u['floor']) if u['floor'] is not None else 0
    except (ValueError, TypeError): floor = 0
    excl = insp['exclusion_list_id'] or '69ce0e91'  # intended-list fallback (link-copy gap)
    return project(u['id'], insp['cycle_id'], excl, floor, insp['cycle_number'])

print("=== ANCHOR VALIDATION ===")
a146 = run_unit('146'); a046 = run_unit('046')
print(f"  Unit 146: {a146} total={sum(a146) if a146 else '?'} (expect 198)")
print(f"  Unit 046: {a046} total={sum(a046) if a046 else '?'} (expect 24)")
ok146 = a146 and sum(a146) == 198
ok046 = a046 and sum(a046) == 24
print(f"  146 OK: {ok146} | 046 OK: {ok046}")
if not (ok146 and ok046):
    print("  !! ANCHOR MISMATCH — output NOT trustworthy, investigate before use.")

# ==========================================================================
# DERIVE THE 27 C2 UNITS (verbatim 69 gates) AND PROJECT EACH
# ==========================================================================
now_sast = dt.utcnow() + td(hours=2)
ANCHOR = dt(2026, 4, 13)
today_mid = dt(now_sast.year, now_sast.month, now_sast.day)
days = (today_mid - ANCHOR).days
idx = 0 if days <= 0 else (days - 1) // 14
snap_mon = ANCHOR + td(days=14 * idx)
snap = ((snap_mon + td(days=1, hours=11, minutes=59)) - td(hours=2)).strftime('%Y-%m-%d %H:%M:%S')

completed = cur.execute("""
  SELECT i.unit_id, MAX(i.cycle_number) m FROM inspection i JOIN unit_real u ON i.unit_id=u.id
  WHERE i.tenant_id=? AND i.review_submitted_at<=? AND i.status IN ('reviewed','approved','pending_followup')
  GROUP BY i.unit_id""", (TENANT_ID, snap)).fetchall()
inspected = set(r['unit_id'] for r in completed)
openr = cur.execute("""
  SELECT d.unit_id, COUNT(*) cnt FROM defect d JOIN unit_real u ON d.unit_id=u.id
  WHERE d.tenant_id=? AND d.created_at<=? AND (d.status='open' OR (d.status='cleared' AND d.cleared_at>?))
    AND d.raised_cycle_id NOT LIKE 'test-%'
    AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id=d.unit_id AND i2.cycle_id=d.raised_cycle_id
        AND i2.status IN ('reviewed','approved','certified','pending_followup') AND i2.review_submitted_at<=?)
  GROUP BY d.unit_id""", (TENANT_ID, snap, snap, snap)).fetchall()
unit_open = {r['unit_id']: r['cnt'] for r in openr}
cyc = {r['unit_id']: r['m'] for r in completed}
c2_ready = [uid for uid in inspected if unit_open.get(uid, 0) == 0 and cyc.get(uid) == 2]

rows = []
for uid in c2_ready:
    u = cur.execute("SELECT unit_number, block, floor FROM unit WHERE id=?", (uid,)).fetchone()
    insp = cur.execute("""SELECT cycle_id, cycle_number, exclusion_list_id FROM inspection
        WHERE unit_id=? AND tenant_id=? AND cycle_number=2 ORDER BY created_at DESC LIMIT 1""",
        (uid, TENANT_ID)).fetchone()
    if not insp:
        print(f"  !! {u['unit_number']}: no C2 inspection"); continue
    try: floor = int(u['floor']) if u['floor'] is not None else 0
    except (ValueError, TypeError): floor = 0
    excl = insp['exclusion_list_id'] or '69ce0e91'  # intended-list fallback (link-copy gap)
    d, l, items = project(uid, insp['cycle_id'], excl, floor, insp['cycle_number'])
    link = 'NULL' if not insp['exclusion_list_id'] else 'LIST'
    rows.append(dict(unit=u['unit_number'], block=u['block'] or '', floor=floor,
                     link=link, defects=d, latents=l, items=items, total=d + l + items))

rows.sort(key=lambda x: (x['total'], x['unit']))
print(f"\n=== 27 C2 COHORT (snapshot {snap}) ===")
print("unit,block,floor,link,defects,latents,items,total")
for r in rows:
    print(f"{r['unit']},{r['block']},{r['floor']},{r['link']},{r['defects']},{r['latents']},{r['items']},{r['total']}")

print(f"\n=== SUMMARY ===")
print(f"Units: {len(rows)} (expect 27)")
tot = [r['total'] for r in rows]
if tot:
    print(f"checkpoints: min={min(tot)} max={max(tot)} avg={sum(tot)/len(tot):.1f} sum={sum(tot)}")
print(f"NULL-link units: {sum(1 for r in rows if r['link']=='NULL')} | LIST: {sum(1 for r in rows if r['link']=='LIST')}")
conn.close()
