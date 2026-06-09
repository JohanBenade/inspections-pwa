#!/usr/bin/env python3
"""
c2c3_actionable_cohort.py  -- READ ONLY, NO MUTATION

Builds the per-unit ACTIONABLE cohort for the 27 units being driven to
full-scope certification.

For each unit:
  - resolves the LATEST inspection (MAX cycle_number, status != not_started),
    matching _route_unit_to_cycle's own logic. (C3 for the 20 Class-A,
    C2 for the 7 NULL-link.)
  - emits ACTIONABLE rows, each reason-tagged:
        PREV_EXCLUDED  - skipped, null-reason, NOT floor-skipped
                         (falls through to inspectable next cycle)
        NOT_INSPECTED  - pending, has_prior_defects = 0
        OPEN_DEFECT    - open b/fwd defect (area/item/comment)
        OPEN_LATENT    - unrectified latent_area_note
  - audit (reconcile to the 55-item intended list 69ce0e91):
        list_size, skipped_live, skipped_inter_list,
        skipped_not_in_list (FLAG), list_not_skipped (FLAG),
        list_linked (the inspection's own exclusion_list_id or None)

Source: /var/data/inspections.db  tenant MONOGRAPH.
RUN ON: RENDER CONSOLE.  Output is printed; paste back to Claude for the xlsx.
"""
import sqlite3, json

DB = '/var/data/inspections.db'
TENANT = 'MONOGRAPH'
INTENDED_LIST = '69ce0e91'   # 55-item intended C2 de-snag list (v401 confirmed)

UNITS = ['014','015','016','023','042','045','049','050','051','052','053',
         '055','056','057','148','227','230','231','233','237','239','241',
         '243','248','250','252','269']

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

def cols(table):
    return [r[1] for r in c.execute('PRAGMA table_info(%s)' % table)]

# ---- schema discovery (no assumptions) -------------------------------------
print('=== SCHEMA DISCOVERY ===')
for t in ('item_template','category','defect','latent_area_note','inspection_item'):
    try:
        print(t, '=>', cols(t))
    except Exception as e:
        print(t, 'ERR', e)
print()

IT_COLS  = cols('item_template')
CAT_COLS = cols('category')
DEF_COLS = cols('defect')
LAT_COLS = cols('latent_area_note')

# area label: category has a name-ish column; pick the first plausible one
def pick(colset, *cands):
    for x in cands:
        if x in colset: return x
    return None

CAT_NAME = pick(CAT_COLS, 'name','category_name','display_name','title','label')
CAT_AREA = pick(CAT_COLS, 'area','area_name','room','group_name')
DEF_AREA = pick(DEF_COLS, 'area','area_name','room')
DEF_ITEM = pick(DEF_COLS, 'item','item_description','item_name','description')
DEF_COMMENT = pick(DEF_COLS, 'comment','description','note','defect_comment')
DEF_STATUS = pick(DEF_COLS, 'status')
DEF_RCN  = pick(DEF_COLS, 'raised_cycle_number')
LAT_AREA = pick(LAT_COLS, 'area_display_name','area','area_name')
LAT_RECT = pick(LAT_COLS, 'rectified_at')
LAT_UNIT = pick(LAT_COLS, 'unit_id')
LAT_NOTE = pick(LAT_COLS, 'note','comment','description')

print('CAT_NAME=%s CAT_AREA=%s DEF_AREA=%s DEF_ITEM=%s DEF_COMMENT=%s DEF_STATUS=%s DEF_RCN=%s'
      % (CAT_NAME,CAT_AREA,DEF_AREA,DEF_ITEM,DEF_COMMENT,DEF_STATUS,DEF_RCN))
print('LAT_AREA=%s LAT_RECT=%s LAT_UNIT=%s LAT_NOTE=%s' % (LAT_AREA,LAT_RECT,LAT_UNIT,LAT_NOTE))
print()

# intended list membership
LIST = set(r[0] for r in c.execute(
    "SELECT item_template_id FROM exclusion_list_item WHERE exclusion_list_id=?",
    [INTENDED_LIST]))
print('intended list %s size = %d' % (INTENDED_LIST, len(LIST)))
print()

def item_label(tid):
    r = c.execute("SELECT item_description, category_id, floor_condition FROM item_template WHERE id=?",[tid]).fetchone()
    if not r: return ('?', '?', None)
    area = '?'
    if r['category_id'] is not None and CAT_NAME:
        cr = c.execute("SELECT %s a FROM category WHERE id=?" % CAT_NAME,[r['category_id']]).fetchone()
        if cr: area = cr['a']
    return (area, r['item_description'], r['floor_condition'])

def latest_insp(uid):
    return c.execute("""SELECT id, cycle_number, status, exclusion_list_id
        FROM inspection WHERE unit_id=? AND tenant_id=?
        AND status NOT IN ('not_started')
        ORDER BY cycle_number DESC LIMIT 1""",[uid,TENANT]).fetchone()

ALL_ROWS = []     # flat dump for the xlsx
SUMMARY = []

for un in UNITS:
    urow = c.execute("SELECT id, floor, block FROM unit WHERE unit_number=? AND tenant_id=?",[un,TENANT]).fetchone()
    if not urow:
        SUMMARY.append({'unit':un,'ERROR':'no unit row'}); continue
    uid, ufloor, ublock = urow['id'], urow['floor'], urow['block']
    insp = latest_insp(uid)
    if not insp:
        SUMMARY.append({'unit':un,'ERROR':'no inspection'}); continue
    iid, icn, istatus, ilist = insp['id'], insp['cycle_number'], insp['status'], insp['exclusion_list_id']

    # live skipped set on this inspection
    skip = set(r[0] for r in c.execute(
        "SELECT item_template_id FROM inspection_item WHERE inspection_id=? AND status='skipped'",[iid]))
    inter   = skip & LIST
    skip_no = skip - LIST          # skipped but NOT on intended list (flag)
    list_no = LIST - skip          # list item NOT skipped (flag)

    # ---- ACTIONABLE: previously excluded (null-reason, not floor-skipped) ----
    # reason via cycle_excluded_item on THIS inspection's cycle
    cyc = c.execute("SELECT cycle_id FROM inspection WHERE id=?",[iid]).fetchone()[0]
    reason_map = {r[0]:r[1] for r in c.execute(
        "SELECT item_template_id, reason FROM cycle_excluded_item WHERE cycle_id=?",[cyc])}
    prev_excl = 0
    for tid in skip:
        area, desc, fc = item_label(tid)
        rsn = reason_map.get(tid)                 # None if not present OR reason NULL
        floor_skip = (fc == 'ground_only' and (ufloor or 0) > 0)
        if rsn is None and not floor_skip:
            prev_excl += 1
            ALL_ROWS.append({'unit':un,'cycle':'C%d'%icn,'reason':'PREV_EXCLUDED',
                             'area':area,'item':desc,'detail':'on intended list' if tid in LIST else 'NOT on list (flag)'})

    # ---- ACTIONABLE: not yet inspected (pending, hpd=0) ----
    not_insp = 0
    for r in c.execute("""SELECT item_template_id FROM inspection_item
            WHERE inspection_id=? AND status='pending' AND COALESCE(has_prior_defects,0)=0""",[iid]):
        area, desc, fc = item_label(r[0]); not_insp += 1
        ALL_ROWS.append({'unit':un,'cycle':'C%d'%icn,'reason':'NOT_INSPECTED',
                         'area':area,'item':desc,'detail':''})

    # ---- ACTIONABLE: open defects (carry forward) ----
    dsel = "SELECT %s area, %s item, %s cmt FROM defect WHERE unit_id=? AND %s='open'" % (
        DEF_AREA or "''", DEF_ITEM or "''", DEF_COMMENT or "''", DEF_STATUS)
    open_def = 0
    for r in c.execute(dsel,[uid]):
        open_def += 1
        ALL_ROWS.append({'unit':un,'cycle':'C%d'%icn,'reason':'OPEN_DEFECT',
                         'area':r['area'],'item':r['item'],'detail':(r['cmt'] or '')[:120]})

    # ---- ACTIONABLE: open latents ----
    open_lat = 0
    if LAT_UNIT and LAT_RECT:
        lsel = "SELECT %s area, %s note FROM latent_area_note WHERE %s=? AND %s IS NULL" % (
            LAT_AREA or "''", LAT_NOTE or "''", LAT_UNIT, LAT_RECT)
        for r in c.execute(lsel,[uid]):
            open_lat += 1
            ALL_ROWS.append({'unit':un,'cycle':'C%d'%icn,'reason':'OPEN_LATENT',
                             'area':r['area'],'item':(r['note'] or '')[:120],'detail':''})

    SUMMARY.append({
        'unit':un,'cycle':'C%d'%icn,'insp_status':istatus,
        'list_linked': ilist or 'NULL',
        'list_size':len(LIST),'skipped_live':len(skip),
        'skip_inter_list':len(inter),
        'skip_NOT_in_list':len(skip_no),
        'list_NOT_skipped':len(list_no),
        'ACT_prev_excl':prev_excl,'ACT_not_insp':not_insp,
        'ACT_open_def':open_def,'ACT_open_lat':open_lat,
        'ACT_total':prev_excl+not_insp+open_def+open_lat,
    })

print('=== PER-UNIT SUMMARY ===')
hdr = ['unit','cycle','insp_status','list_linked','list_size','skipped_live',
       'skip_inter_list','skip_NOT_in_list','list_NOT_skipped',
       'ACT_prev_excl','ACT_not_insp','ACT_open_def','ACT_open_lat','ACT_total']
print('\t'.join(hdr))
for s in SUMMARY:
    if 'ERROR' in s:
        print(s['unit'],'ERROR',s['ERROR']); continue
    print('\t'.join(str(s[h]) for h in hdr))

print()
print('=== FLAT ACTIONABLE ROWS (json, for xlsx) ===')
print('ROWCOUNT', len(ALL_ROWS))
print(json.dumps(ALL_ROWS))
