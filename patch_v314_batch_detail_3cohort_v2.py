#!/usr/bin/env python3
"""v314 -- canonical 3-cohort checkpoints denominator for C2+ units on batch detail.

(v2: OP 2 anchor narrowed to just the addressed counter line. The prior
anchor included a blank line + 'for u in units:' which only matched in
detail() -- detail_data() has no blank line at that spot.)

Both detail() and detail_data() in batches.py compute u['checkpoints'] as
defect_bfwd for C2+ units, which counts every prior-cycle defect regardless
of whether it has already been cleared in earlier cycles. This is the
pre-v310 pattern that survives in batch detail because v310 was localised
to _build_live_monitor_data only.

Fix: for C2+ units, set u['checkpoints'] = items_action + open_prior_latents
+ defect_bfwd_action, matching the live-monitor cohort union from v310.

Each op uses assert count == 2 because detail() and detail_data() have
identical duplicated bodies for the patched sections (per HANDOVER v309
section 1.3). Single str.replace replaces both occurrences atomically.

Idempotent: re-running is a no-op once applied.
"""
from pathlib import Path
import ast

FILE = Path('app/routes/batches.py')
content = FILE.read_text()
original = content


def apply_op(label, marker_present, old, new):
    """Apply a single op: skip if marker_present in content, else replace
    both occurrences atomically with assert count == 2."""
    global content
    if marker_present in content:
        print(f'{label}: already applied (idempotent skip)')
        return
    n = content.count(old)
    assert n == 2, f'{label}: expected 2 matches, got {n}'
    content = content.replace(old, new)
    print(f'{label}: replaced 2 occurrences')


# === OP 1: expand d_map init dict to include defect_bfwd_action counter ===
OLD_1 = (
    "                d_map[d_uid] = {'defect_bfwd': 0, 'defect_cleared': 0, "
    "'defect_new': 0, 'defect_open': 0, 'defect_addressed': 0}"
)
NEW_1 = (
    "                d_map[d_uid] = {'defect_bfwd': 0, 'defect_cleared': 0, "
    "'defect_new': 0, 'defect_open': 0, 'defect_addressed': 0, "
    "'defect_bfwd_action': 0}"
)
apply_op(
    'OP 1 (d_map init)',
    "'defect_addressed': 0, 'defect_bfwd_action': 0}\n",
    OLD_1, NEW_1,
)

# === OP 2: add defect_bfwd_action counter logic in d_map population loop ===
# Anchor on the addressed counter line ONLY (no surrounding context) so the
# replace works in both detail() and detail_data() regardless of the blank
# line that detail() has but detail_data() lacks before 'for u in units:'.
OLD_2 = "                d_map[d_uid]['defect_addressed'] += dr['cnt']"
NEW_2 = (
    "                d_map[d_uid]['defect_addressed'] += dr['cnt']\n"
    "            # v314: b/fwd defect needing action this cycle (open OR cleared this cycle)\n"
    "            if d_rcn < d_cn and (dr['status'] == 'open' or d_ccn == d_cn):\n"
    "                d_map[d_uid]['defect_bfwd_action'] += dr['cnt']"
)
apply_op(
    'OP 2 (defect_bfwd_action counter)',
    "d_map[d_uid]['defect_bfwd_action'] += dr['cnt']",
    OLD_2, NEW_2,
)

# === OP 3: expand u.update fallback dict to include defect_bfwd_action ===
OLD_3 = (
    "            u.update(d_map.get(u['unit_id'], "
    "{'defect_bfwd': 0, 'defect_cleared': 0, 'defect_new': 0, "
    "'defect_open': 0, 'defect_addressed': 0}))"
)
NEW_3 = (
    "            u.update(d_map.get(u['unit_id'], "
    "{'defect_bfwd': 0, 'defect_cleared': 0, 'defect_new': 0, "
    "'defect_open': 0, 'defect_addressed': 0, 'defect_bfwd_action': 0}))"
)
apply_op(
    'OP 3 (u.update fallback dict)',
    "'defect_addressed': 0, 'defect_bfwd_action': 0}))",
    OLD_3, NEW_3,
)

# === OP 4a: extend items query SELECT to compute items_action too ===
OLD_4a = (
    "            SELECT inspection_id,\n"
    "                   SUM(CASE WHEN status NOT IN ('pending', 'skipped') "
    "THEN 1 ELSE 0 END) AS items_marked\n"
    "            FROM inspection_item"
)
NEW_4a = (
    "            SELECT inspection_id,\n"
    "                   SUM(CASE WHEN status NOT IN ('pending', 'skipped') "
    "THEN 1 ELSE 0 END) AS items_marked,\n"
    "                   SUM(CASE WHEN status != 'skipped' "
    "AND COALESCE(has_prior_defects, 0) = 0\n"
    "                              AND (status = 'pending' OR marked_at IS NOT NULL) "
    "THEN 1 ELSE 0 END) AS items_action\n"
    "            FROM inspection_item"
)
apply_op(
    'OP 4a (items SELECT extended)',
    'AS items_action',
    OLD_4a, NEW_4a,
)

# === OP 4b: restructure items_map from flat to nested dict ===
OLD_4b = (
    "        items_map = {r['inspection_id']: (r['items_marked'] or 0) "
    "for r in ii_rows}"
)
NEW_4b = (
    "        items_map = {r['inspection_id']: "
    "{'items_marked': r['items_marked'] or 0, "
    "'items_action': r['items_action'] or 0} for r in ii_rows}"
)
apply_op(
    'OP 4b (items_map nested)',
    "'items_action': r['items_action']",
    OLD_4b, NEW_4b,
)

# === OP 4c: extend items extraction loop + add canonical C2+ override pass ===
OLD_4c = (
    "    for u in units:\n"
    "        u['items_marked'] = items_map.get(u.get('inspection_id'), 0)"
)
NEW_4c = (
    "    for u in units:\n"
    "        m = items_map.get(u.get('inspection_id'), {})\n"
    "        u['items_marked'] = m.get('items_marked', 0)\n"
    "        u['items_action'] = m.get('items_action', 0)\n"
    "\n"
    "    # v314: canonical 3-cohort checkpoints for C2+ units\n"
    "    # cohort = newly-visible items + open b/fwd latents + b/fwd defects needing action\n"
    "    # matches the live-monitor union in _build_live_monitor_data (v310)\n"
    "    for u in units:\n"
    "        if (u.get('cycle_number') or 1) > 1:\n"
    "            u['checkpoints'] = u['items_action'] + u['open_prior_latents'] "
    "+ u.get('defect_bfwd_action', 0)\n"
    "            u['unit_checkpoints'] = u['checkpoints']\n"
    "    total_checkpoints = sum(u.get('unit_checkpoints', 0) for u in units)"
)
apply_op(
    'OP 4c (items extraction + C2+ override pass)',
    "u['items_action'] = m.get('items_action', 0)",
    OLD_4c, NEW_4c,
)

# === Python syntax (AST) check ===
try:
    ast.parse(content)
    print('python syntax: OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR (file NOT written): {e}')
    raise SystemExit(1)

# === write file ===
if content != original:
    FILE.write_text(content)
    print(f'wrote {FILE} ({len(content)} chars)')
else:
    print('no changes (all ops were no-ops)')
