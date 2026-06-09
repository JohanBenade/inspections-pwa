#!/usr/bin/env python3
"""
c2c3_actionable_cohort.py  -- READ ONLY, NO MUTATION  (v402 rewrite)

Builds the per-unit ACTIONABLE cohort for the 27 units being driven to
full-scope certification.

CHANGES FROM PRIOR VERSION (v402 sec 1/2):
  - Area label fixed: item_template.category_id -> category_template.id
    -> category_template.area_id -> area_template.id (area_name).
    (The old 'category' table does NOT exist; it is category_template +
    area_template. Verified by PRAGMA this session.)
  - NO list-as-filter. The 55-item list 69ce0e91 is a per-unit AUDIT column
    only; it never gates rows. (No exclusions apply now.)
  - defect / latent area labels resolved through the SAME verified chain
    (defect.item_template_id ; latent_area_note.area_template_id), NOT via
    guessed area columns on those tables.
  - Pending split (option 1): hpd=0 = NOT_INSPECTED ;
    hpd=1 = NOT_INSPECTED_DEFECT_TRACK (defect-owned, flagged separately).

For each unit:
  - resolves the LATEST inspection (MAX cycle_number, status != not_started).
    (C3 for the 20 Class-A, C2 for the 7 NULL-link.)
  - emits ACTIONABLE rows, each reason-tagged:
        PREV_EXCLUDED                - skipped, null-reason, NOT floor-skipped
        NOT_INSPECTED                - pending, has_prior_defects = 0
        NOT_INSPECTED_DEFECT_TRACK   - pending, has_prior_defects = 1
        OPEN_DEFECT                  - open b/fwd defect
        OPEN_LATENT                  - unrectified latent_area_note
  - audit (reconcile to the 55-item intended list 69ce0e91), AUDIT ONLY:
        list_size, skipped_live, skip_inter_list,
        skip_NOT_in_list, list_NOT_skipped, list_linked

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
    try:
        return [r[1] for r in c.execute('PRAGMA table_info(%s)' % table)]
    except Exception as e:
        return ['ERR:%s' % e]

# ---- schema discovery (no assumptions) -------------------------------------
print('=== SCHEMA DISCOVERY ===')
for t in ('item_template','category_template','area_template','defect',
          'latent_area_note','inspection_item','cycle_excluded_item',
          'exclusion_list_item','inspection','unit'):
    print(t, '=>', cols(t))
print()

# ---- area resolution chain (VERIFIED this session) -------------------------
# Build one lookup: item_template_id -> (area_name, category_name, floor_condition)
AREA_BY_ITEM = {}
for r in c.execute("""
        SELECT it.id AS tid, it.floor_condition AS fc,
               ct.category_name AS cat, at.area_name AS area
        FROM item_template it
        LEFT JOIN category_template ct ON ct.id = it.category_id
        LEFT JOIN area_template at ON at.id = ct.area_id
        WHERE it.tenant_id=?""", [TENANT]):
    AREA_BY_ITEM[r['tid']] = (r['area'] or '?', r['cat'] or '?', r['fc'])

def item_label(tid):
    return AREA_BY_ITEM.get(tid, ('?', '?', None))

# area_template_id -> area_name (for latents)
AREA_BY_AT = {r['id']: r['area_name']
              for r in c.execute(
                  "SELECT id, area_name FROM area_template WHERE tenant_id=?", [TENANT])}

# intended list membership (AUDIT ONLY)
LIST = set(r[0] for r in c.execute(
    "SELECT item_template_id FROM exclusion_list_item WHERE exclusion_list_id=?",
    [INTENDED_LIST]))
print('intended list %s size = %d  (AUDIT ONLY, not a filter)' % (INTENDED_LIST, len(LIST)))
print()

def latest_insp(uid):
    return c.execute("""SELECT id, cycle_id, cycle_number, status, exclusion_list_id
        FROM inspection WHERE unit_id=? AND tenant_id=?
        AND status NOT IN ('not_started')
        ORDER BY cycle_number DESC LIMIT 1""", [uid, TENANT]).fetchone()

ALL_ROWS = []     # flat dump for the xlsx
SUMMARY = []

for un in UNITS:
    urow = c.execute("SELECT id, floor, block FROM unit WHERE unit_number=? AND tenant_id=?",
                     [un, TENANT]).fetchone()
    if not urow:
        SUMMARY.append({'unit': un, 'ERROR': 'no unit row'}); continue
    uid, ufloor, ublock = urow['id'], urow['floor'], urow['block']
    insp = latest_insp(uid)
    if not insp:
        SUMMARY.append({'unit': un, 'ERROR': 'no inspection'}); continue
    iid, icyc, icn, istatus, ilist = (insp['id'], insp['cycle_id'],
                                      insp['cycle_number'], insp['status'],
                                      insp['exclusion_list_id'])

    # live skipped set on this inspection
    skip = set(r[0] for r in c.execute(
        "SELECT item_template_id FROM inspection_item WHERE inspection_id=? AND status='skipped'", [iid]))
    inter   = skip & LIST
    skip_no = skip - LIST          # skipped but NOT on intended list (audit flag)
    list_no = LIST - skip          # list item NOT skipped (audit flag)

    # cycle_excluded_item reason map for THIS inspection's cycle
    reason_map = {r[0]: r[1] for r in c.execute(
        "SELECT item_template_id, reason FROM cycle_excluded_item WHERE cycle_id=?", [icyc])}

    # ---- ACTIONABLE: previously excluded (null-reason, not floor-skipped) ----
    prev_excl = 0
    for tid in skip:
        area, cat, fc = item_label(tid)
        rsn = reason_map.get(tid)                 # None if absent OR reason NULL
        floor_skip = (fc == 'ground_only' and (ufloor or 0) > 0)
        if rsn is None and not floor_skip:
            prev_excl += 1
            ALL_ROWS.append({'unit': un, 'cycle': 'C%d' % icn, 'reason': 'PREV_EXCLUDED',
                             'area': area, 'category': cat, 'item': '', 'detail': ''})

    # ---- ACTIONABLE: not yet inspected (pending) -- option 1 split -----------
    not_insp = 0
    not_insp_dt = 0
    for r in c.execute("""SELECT item_template_id, COALESCE(has_prior_defects,0) AS hpd
            FROM inspection_item WHERE inspection_id=? AND status='pending'""", [iid]):
        area, cat, fc = item_label(r['item_template_id'])
        if r['hpd'] == 1:
            not_insp_dt += 1
            ALL_ROWS.append({'unit': un, 'cycle': 'C%d' % icn,
                             'reason': 'NOT_INSPECTED_DEFECT_TRACK',
                             'area': area, 'category': cat, 'item': '', 'detail': 'defect-track owned'})
        else:
            not_insp += 1
            ALL_ROWS.append({'unit': un, 'cycle': 'C%d' % icn, 'reason': 'NOT_INSPECTED',
                             'area': area, 'category': cat, 'item': '', 'detail': ''})

    # ---- ACTIONABLE: open defects (carry forward) ----
    open_def = 0
    for r in c.execute("""SELECT item_template_id, original_comment, raw_comment,
                                 reviewed_comment, defect_type
            FROM defect WHERE unit_id=? AND tenant_id=? AND status='open'""", [uid, TENANT]):
        area, cat, fc = item_label(r['item_template_id'])
        cmt = r['reviewed_comment'] or r['original_comment'] or r['raw_comment'] or ''
        open_def += 1
        ALL_ROWS.append({'unit': un, 'cycle': 'C%d' % icn, 'reason': 'OPEN_DEFECT',
                         'area': area, 'category': cat,
                         'item': r['defect_type'] or '', 'detail': cmt[:160]})

    # ---- ACTIONABLE: open latents ----
    open_lat = 0
    for r in c.execute("""SELECT area_template_id, area_name_override, note_html
            FROM latent_area_note WHERE unit_id=? AND tenant_id=? AND rectified_at IS NULL""",
            [uid, TENANT]):
        area = r['area_name_override'] or AREA_BY_AT.get(r['area_template_id'], '?')
        open_lat += 1
        ALL_ROWS.append({'unit': un, 'cycle': 'C%d' % icn, 'reason': 'OPEN_LATENT',
                         'area': area, 'category': 'LATENT',
                         'item': '', 'detail': (r['note_html'] or '')[:160]})

    SUMMARY.append({
        'unit': un, 'cycle': 'C%d' % icn, 'insp_status': istatus,
        'list_linked': ilist or 'NULL',
        'list_size': len(LIST), 'skipped_live': len(skip),
        'skip_inter_list': len(inter),
        'skip_NOT_in_list': len(skip_no),
        'list_NOT_skipped': len(list_no),
        'ACT_prev_excl': prev_excl, 'ACT_not_insp': not_insp,
        'ACT_not_insp_dt': not_insp_dt,
        'ACT_open_def': open_def, 'ACT_open_lat': open_lat,
        'ACT_total': prev_excl + not_insp + not_insp_dt + open_def + open_lat,
    })

print('=== PER-UNIT SUMMARY ===')
hdr = ['unit', 'cycle', 'insp_status', 'list_linked', 'list_size', 'skipped_live',
       'skip_inter_list', 'skip_NOT_in_list', 'list_NOT_skipped',
       'ACT_prev_excl', 'ACT_not_insp', 'ACT_not_insp_dt',
       'ACT_open_def', 'ACT_open_lat', 'ACT_total']
print('\t'.join(hdr))
for s in SUMMARY:
    if 'ERROR' in s:
        print(s['unit'], 'ERROR', s['ERROR']); continue
    print('\t'.join(str(s[h]) for h in hdr))

print()
print('=== FLAT ACTIONABLE ROWS (json, for xlsx) ===')
print('ROWCOUNT', len(ALL_ROWS))
print(json.dumps(ALL_ROWS))
