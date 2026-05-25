#!/usr/bin/env python3
"""v314b -- canonical 3-cohort numerator on batch detail (u.checkpoint_marked)
          + latent denominator gap fix.

v314 made u.checkpoints the canonical 3-cohort DENOMINATOR for C2+ units, but
two things remained wrong:

(a) NUMERATOR for C2+ on batch detail was u.defect_addressed (defects only)
    -- under-counts work for actively-progressed C2+ units (missed items
    marked + latents addressed).

(b) The latent query filtered rectified_at_cycle_id IS NULL, so open_prior_
    latents excluded latents that were rectified THIS cycle. Per v310's
    cohort definition the "open at start of current cycle" set must include
    those (they were open at the start, they just got addressed). This made
    the canonical denominator under-count too.

This patch fixes both, plus adds a canonical numerator field
(u.checkpoint_marked = items_action_marked + lan_addressed +
defect_bfwd_addressed), and points the template at the canonical
num/den fields for C2+ units.

Applied to BOTH detail() and detail_data() in batches.py (assert count == 2
per op) and to _detail_tbody.html (count == 1).

Idempotent: re-running is a no-op once applied.
"""
from pathlib import Path
import ast
from jinja2 import Environment, TemplateSyntaxError

BATCHES = Path('app/routes/batches.py')
TBODY = Path('app/templates/batches/_detail_tbody.html')

batches_content = BATCHES.read_text()
tbody_content = TBODY.read_text()
batches_original = batches_content
tbody_original = tbody_content


def apply_op(file_label, content, label, marker_present, old, new, expected_count):
    """Generic op runner. Returns updated content (or unchanged if skipped)."""
    if marker_present in content:
        print(f'{file_label} {label}: already applied (idempotent skip)')
        return content
    n = content.count(old)
    assert n == expected_count, (
        f'{file_label} {label}: expected {expected_count} matches, got {n}'
    )
    new_content = content.replace(old, new)
    print(f'{file_label} {label}: replaced {expected_count} occurrence(s)')
    return new_content


# ============================================================================
# batches.py changes
# ============================================================================

# OP 1: d_map init dict -- add defect_bfwd_addressed counter
OLD_1 = (
    "                d_map[d_uid] = {'defect_bfwd': 0, 'defect_cleared': 0, "
    "'defect_new': 0, 'defect_open': 0, 'defect_addressed': 0, "
    "'defect_bfwd_action': 0}"
)
NEW_1 = (
    "                d_map[d_uid] = {'defect_bfwd': 0, 'defect_cleared': 0, "
    "'defect_new': 0, 'defect_open': 0, 'defect_addressed': 0, "
    "'defect_bfwd_action': 0, 'defect_bfwd_addressed': 0}"
)
batches_content = apply_op(
    'batches.py', batches_content,
    'OP 1 (d_map init: defect_bfwd_addressed)',
    "'defect_bfwd_action': 0, 'defect_bfwd_addressed': 0}\n",
    OLD_1, NEW_1, 2,
)

# OP 2: d_map population loop -- add defect_bfwd_addressed counter logic
# Insert after the defect_bfwd_action counter line (added by v314).
OLD_2 = (
    "            if d_rcn < d_cn and (dr['status'] == 'open' or d_ccn == d_cn):\n"
    "                d_map[d_uid]['defect_bfwd_action'] += dr['cnt']"
)
NEW_2 = (
    "            if d_rcn < d_cn and (dr['status'] == 'open' or d_ccn == d_cn):\n"
    "                d_map[d_uid]['defect_bfwd_action'] += dr['cnt']\n"
    "            # v314b: b/fwd defect addressed this cycle (any status, "
    "addressed_cycle_number matches)\n"
    "            if d_rcn < d_cn and dr['addressed_cycle_number'] == d_cn:\n"
    "                d_map[d_uid]['defect_bfwd_addressed'] += dr['cnt']"
)
batches_content = apply_op(
    'batches.py', batches_content,
    'OP 2 (defect_bfwd_addressed counter)',
    "d_map[d_uid]['defect_bfwd_addressed'] += dr['cnt']",
    OLD_2, NEW_2, 2,
)

# OP 3: u.update fallback dict -- add defect_bfwd_addressed
OLD_3 = (
    "            u.update(d_map.get(u['unit_id'], "
    "{'defect_bfwd': 0, 'defect_cleared': 0, 'defect_new': 0, "
    "'defect_open': 0, 'defect_addressed': 0, 'defect_bfwd_action': 0}))"
)
NEW_3 = (
    "            u.update(d_map.get(u['unit_id'], "
    "{'defect_bfwd': 0, 'defect_cleared': 0, 'defect_new': 0, "
    "'defect_open': 0, 'defect_addressed': 0, 'defect_bfwd_action': 0, "
    "'defect_bfwd_addressed': 0}))"
)
batches_content = apply_op(
    'batches.py', batches_content,
    'OP 3 (u.update fallback dict: defect_bfwd_addressed)',
    "'defect_bfwd_action': 0, 'defect_bfwd_addressed': 0}))",
    OLD_3, NEW_3, 2,
)

# OP 4: items SQL -- add items_action_marked field
OLD_4 = (
    "                   SUM(CASE WHEN status != 'skipped' "
    "AND COALESCE(has_prior_defects, 0) = 0\n"
    "                              AND (status = 'pending' OR marked_at IS NOT NULL) "
    "THEN 1 ELSE 0 END) AS items_action"
)
NEW_4 = (
    "                   SUM(CASE WHEN status != 'skipped' "
    "AND COALESCE(has_prior_defects, 0) = 0\n"
    "                              AND (status = 'pending' OR marked_at IS NOT NULL) "
    "THEN 1 ELSE 0 END) AS items_action,\n"
    "                   SUM(CASE WHEN status NOT IN ('pending', 'skipped') "
    "AND COALESCE(has_prior_defects, 0) = 0\n"
    "                              AND marked_at IS NOT NULL "
    "THEN 1 ELSE 0 END) AS items_action_marked"
)
batches_content = apply_op(
    'batches.py', batches_content,
    'OP 4 (items SQL: items_action_marked)',
    'AS items_action_marked',
    OLD_4, NEW_4, 2,
)

# OP 5: items_map nested dict -- add items_action_marked field
OLD_5 = (
    "        items_map = {r['inspection_id']: "
    "{'items_marked': r['items_marked'] or 0, "
    "'items_action': r['items_action'] or 0} for r in ii_rows}"
)
NEW_5 = (
    "        items_map = {r['inspection_id']: "
    "{'items_marked': r['items_marked'] or 0, "
    "'items_action': r['items_action'] or 0, "
    "'items_action_marked': r['items_action_marked'] or 0} for r in ii_rows}"
)
batches_content = apply_op(
    'batches.py', batches_content,
    'OP 5 (items_map: items_action_marked field)',
    "'items_action_marked': r['items_action_marked']",
    OLD_5, NEW_5, 2,
)

# OP 6: items extraction loop -- set u['items_action_marked']
OLD_6 = (
    "    for u in units:\n"
    "        m = items_map.get(u.get('inspection_id'), {})\n"
    "        u['items_marked'] = m.get('items_marked', 0)\n"
    "        u['items_action'] = m.get('items_action', 0)"
)
NEW_6 = (
    "    for u in units:\n"
    "        m = items_map.get(u.get('inspection_id'), {})\n"
    "        u['items_marked'] = m.get('items_marked', 0)\n"
    "        u['items_action'] = m.get('items_action', 0)\n"
    "        u['items_action_marked'] = m.get('items_action_marked', 0)"
)
batches_content = apply_op(
    'batches.py', batches_content,
    'OP 6 (items extraction: items_action_marked)',
    "u['items_action_marked'] = m.get('items_action_marked', 0)",
    OLD_6, NEW_6, 2,
)

# OP 7: replace the entire latent block.
# Old block: filters rectified_at_cycle_id IS NULL (under-counts denominator
#   for rectified-this-cycle latents), and only exposes open_prior_latents.
# New block: comprehensive query that captures both
#   open_at_start (denominator) and addressed_this_cycle (numerator).
OLD_7 = (
    "    # --- Unit Checkpoints column (baseline - exclusions + open prior latents) ---\n"
    "    lan_map = {}\n"
    "    if units:\n"
    "        lan_unit_ids = list(set(u['unit_id'] for u in units))\n"
    "        lan_ph = ','.join(['?'] * len(lan_unit_ids))\n"
    "        lan_rows = query_db(f"
    '"""'
    "\n"
    "            SELECT unit_id, cycle_number, COUNT(*) AS cnt\n"
    "            FROM latent_area_note\n"
    "            WHERE tenant_id = ?\n"
    "              AND unit_id IN ({lan_ph})\n"
    "              AND rectified_at_cycle_id IS NULL\n"
    "            GROUP BY unit_id, cycle_number\n"
    "        "
    '"""'
    ", [tenant_id] + lan_unit_ids)\n"
    "        for lr in lan_rows:\n"
    "            lan_map.setdefault(lr['unit_id'], {})[lr['cycle_number']] = lr['cnt']\n"
    "\n"
    "    for u in units:\n"
    "        unit_cycle = u.get('cycle_number') or 1\n"
    "        u['open_prior_latents'] = sum(\n"
    "            cnt for cn, cnt in lan_map.get(u['unit_id'], {}).items() if cn < unit_cycle\n"
    "        )\n"
    "        u['unit_checkpoints'] = u['checkpoints'] + u['open_prior_latents']\n"
    "\n"
    "    total_checkpoints = sum(u.get('unit_checkpoints', 0) for u in units)"
)
NEW_7 = (
    "    # v314b: latent ledger -- open at start of cycle (denominator) "
    "+ addressed this cycle (numerator).\n"
    "    # Single comprehensive query, dual-purpose aggregation in Python.\n"
    "    lan_open_map = {}\n"
    "    lan_addressed_map = {}\n"
    "    if units:\n"
    "        lan_unit_ids = list(set(u['unit_id'] for u in units))\n"
    "        lan_ph = ','.join(['?'] * len(lan_unit_ids))\n"
    "        lan_rows = query_db(f"
    '"""'
    "\n"
    "            SELECT unit_id, cycle_number, rectified_at_cycle_number, "
    "addressed_cycle_number,\n"
    "                   CASE WHEN rectified_at IS NULL THEN 1 ELSE 0 END AS is_not_rectified,\n"
    "                   COUNT(*) AS cnt\n"
    "            FROM latent_area_note\n"
    "            WHERE tenant_id = ?\n"
    "              AND unit_id IN ({lan_ph})\n"
    "            GROUP BY unit_id, cycle_number, rectified_at_cycle_number, "
    "addressed_cycle_number, is_not_rectified\n"
    "        "
    '"""'
    ", [tenant_id] + lan_unit_ids)\n"
    "        u_cycle_map = {u['unit_id']: (u.get('cycle_number') or 1) for u in units}\n"
    "        for lr in lan_rows:\n"
    "            uid = lr['unit_id']\n"
    "            unit_cycle = u_cycle_map.get(uid, 1)\n"
    "            # b/fwd only\n"
    "            if (lr['cycle_number'] or 0) >= unit_cycle:\n"
    "                continue\n"
    "            # open at start of current cycle: not rectified OR rectified this cycle\n"
    "            if lr['is_not_rectified'] or lr['rectified_at_cycle_number'] == unit_cycle:\n"
    "                lan_open_map[uid] = lan_open_map.get(uid, 0) + lr['cnt']\n"
    "            # addressed this cycle: rectified this cycle, OR still-open AND addressed this cycle\n"
    "            if (lr['rectified_at_cycle_number'] == unit_cycle or\n"
    "                    (lr['addressed_cycle_number'] == unit_cycle and lr['is_not_rectified'])):\n"
    "                lan_addressed_map[uid] = lan_addressed_map.get(uid, 0) + lr['cnt']\n"
    "\n"
    "    for u in units:\n"
    "        u['open_prior_latents'] = lan_open_map.get(u['unit_id'], 0)\n"
    "        u['lan_addressed'] = lan_addressed_map.get(u['unit_id'], 0)\n"
    "        u['unit_checkpoints'] = u['checkpoints'] + u['open_prior_latents']\n"
    "\n"
    "    total_checkpoints = sum(u.get('unit_checkpoints', 0) for u in units)"
)
batches_content = apply_op(
    'batches.py', batches_content,
    'OP 7 (latent ledger: dual-purpose open/addressed)',
    "lan_open_map.get(u['unit_id'], 0)",
    OLD_7, NEW_7, 2,
)

# OP 8: C2+ override pass -- also expose canonical u['checkpoint_marked']
OLD_8 = (
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
NEW_8 = (
    "    # v314: canonical 3-cohort checkpoints for C2+ units\n"
    "    # cohort = newly-visible items + open b/fwd latents + b/fwd defects needing action\n"
    "    # matches the live-monitor union in _build_live_monitor_data (v310)\n"
    "    # v314b: also expose checkpoint_marked (canonical numerator) so template\n"
    "    # progress fraction is consistent num/den (was defects-only before).\n"
    "    for u in units:\n"
    "        if (u.get('cycle_number') or 1) > 1:\n"
    "            u['checkpoints'] = u['items_action'] + u['open_prior_latents'] "
    "+ u.get('defect_bfwd_action', 0)\n"
    "            u['checkpoint_marked'] = u.get('items_action_marked', 0) "
    "+ u.get('lan_addressed', 0) + u.get('defect_bfwd_addressed', 0)\n"
    "            u['unit_checkpoints'] = u['checkpoints']\n"
    "    total_checkpoints = sum(u.get('unit_checkpoints', 0) for u in units)"
)
batches_content = apply_op(
    'batches.py', batches_content,
    'OP 8 (C2+ override: expose checkpoint_marked)',
    "u['checkpoint_marked'] = u.get('items_action_marked', 0)",
    OLD_8, NEW_8, 2,
)

# === Python syntax check on batches.py ===
try:
    ast.parse(batches_content)
    print('batches.py python syntax: OK')
except SyntaxError as e:
    print(f'BATCHES.PY SYNTAX ERROR (files NOT written): {e}')
    raise SystemExit(1)


# ============================================================================
# _detail_tbody.html changes
# ============================================================================

# OP T1: C2+ progress branch -- use canonical num and den
OLD_T1 = (
    "            {% if cn > 1 %}\n"
    "                {% set num = u.defect_addressed or 0 %}\n"
    "                {% set den = u.defect_bfwd or 0 %}\n"
    "            {% else %}"
)
NEW_T1 = (
    "            {% if cn > 1 %}\n"
    "                {% set num = u.checkpoint_marked or 0 %}\n"
    "                {% set den = u.checkpoints or 0 %}\n"
    "            {% else %}"
)
tbody_content = apply_op(
    '_detail_tbody.html', tbody_content,
    'OP T1 (C2+ branch: canonical num/den)',
    "{% set num = u.checkpoint_marked or 0 %}",
    OLD_T1, NEW_T1, 1,
)

# === Jinja syntax check on _detail_tbody.html ===
try:
    Environment().parse(tbody_content)
    print('_detail_tbody.html jinja syntax: OK')
except TemplateSyntaxError as e:
    print(f'TBODY JINJA ERROR (files NOT written): {e}')
    raise SystemExit(1)


# ============================================================================
# Write both files (atomic at this point: all ops + syntax checks passed)
# ============================================================================

if batches_content != batches_original:
    BATCHES.write_text(batches_content)
    print(f'wrote {BATCHES} ({len(batches_content)} chars)')
else:
    print(f'{BATCHES}: no changes (all ops were no-ops)')

if tbody_content != tbody_original:
    TBODY.write_text(tbody_content)
    print(f'wrote {TBODY} ({len(tbody_content)} chars)')
else:
    print(f'{TBODY}: no changes (all ops were no-ops)')
