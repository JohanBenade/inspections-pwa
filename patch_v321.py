#!/usr/bin/env python3
"""
patch_v321.py - SMB section 07 (Worst Units) live-data leak fix.

Two changes inside the SMB data-builder function in app/routes/analytics.py:

  Change A (SQL): Add `AND i.review_submitted_at <= ?` snapshot gate to the two
                  subqueries inside the stuck_rows query (first_c1_submitted and
                  max_cycle). This matches the EXISTS clause's snapshot gate at
                  L6294 and freezes the cycle column. Adjust param list to add
                  two snapshot_str values at the front (matching new placeholder
                  positions).

  Change B (Python): Replace live _dt.now() in the weeks calculation with a
                     snapshot_dt_naive computed once from snapshot_str. Freezes
                     the WKS SINCE C1 column.

Run from repo root:
    python3 patch_v321.py
"""

from pathlib import Path

TARGET = Path("app/routes/analytics.py")
assert TARGET.exists(), "ABORT: target not found - run this script from repo root"

content = TARGET.read_text()

# ---------------------------------------------------------------------------
# Change A: SQL block
# ---------------------------------------------------------------------------

old_sql = '''    stuck_rows = query_db("""
        SELECT u.unit_number, u.block, u.floor,
               COUNT(d.id) as open_count,
               (SELECT MIN(i.submitted_at) FROM inspection i WHERE i.unit_id = u.id AND i.tenant_id = d.tenant_id AND i.status IN ('reviewed','approved','pending_followup')) as first_c1_submitted,
               (SELECT MAX(i.cycle_number) FROM inspection i WHERE i.unit_id = u.id AND i.tenant_id = d.tenant_id AND i.status IN ('reviewed','approved','pending_followup')) as max_cycle,
               SUM(CASE WHEN d.raised_cycle_number >= 2 THEN 1 ELSE 0 END) as new_c2
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.created_at <= ?
        AND (d.status = 'open' OR (d.status = 'cleared' AND d.cleared_at > ?))
        AND d.raised_cycle_id NOT LIKE 'test-%%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup') AND i2.review_submitted_at <= ?)
        GROUP BY u.id
        ORDER BY open_count DESC
    """, [tenant_id, snapshot_str, snapshot_str, snapshot_str])'''

new_sql = '''    # v321: subqueries gated by review_submitted_at <= snapshot (matches EXISTS clause)
    stuck_rows = query_db("""
        SELECT u.unit_number, u.block, u.floor,
               COUNT(d.id) as open_count,
               (SELECT MIN(i.submitted_at) FROM inspection i WHERE i.unit_id = u.id AND i.tenant_id = d.tenant_id AND i.status IN ('reviewed','approved','pending_followup') AND i.review_submitted_at <= ?) as first_c1_submitted,
               (SELECT MAX(i.cycle_number) FROM inspection i WHERE i.unit_id = u.id AND i.tenant_id = d.tenant_id AND i.status IN ('reviewed','approved','pending_followup') AND i.review_submitted_at <= ?) as max_cycle,
               SUM(CASE WHEN d.raised_cycle_number >= 2 THEN 1 ELSE 0 END) as new_c2
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.created_at <= ?
        AND (d.status = 'open' OR (d.status = 'cleared' AND d.cleared_at > ?))
        AND d.raised_cycle_id NOT LIKE 'test-%%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup') AND i2.review_submitted_at <= ?)
        GROUP BY u.id
        ORDER BY open_count DESC
    """, [snapshot_str, snapshot_str, tenant_id, snapshot_str, snapshot_str, snapshot_str])'''

assert old_sql in content, "ABORT: Change A old SQL block did not match"
assert content.count(old_sql) == 1, "ABORT: Change A old SQL block matched multiple times"
content = content.replace(old_sql, new_sql)
print("OK Change A applied (SQL: snapshot gate added to subqueries)")

# ---------------------------------------------------------------------------
# Change B: Python weeks calculation
# ---------------------------------------------------------------------------

old_py = """    stuck_units = []
    total_stuck_defects = 0
    oldest_weeks = 0
    for r in stuck_rows:
        weeks = 0
        if r['first_c1_submitted']:
            try:
                sub_dt = _dt.fromisoformat(r['first_c1_submitted'].replace('Z', '+00:00') if 'Z' in r['first_c1_submitted'] else r['first_c1_submitted'])
                weeks = max(0, (_dt.now(sub_dt.tzinfo) - sub_dt).days // 7) if sub_dt.tzinfo else max(0, (_dt.now() - sub_dt).days // 7)
            except (ValueError, TypeError):
                weeks = 0"""

new_py = """    stuck_units = []
    total_stuck_defects = 0
    oldest_weeks = 0
    # v321: compute weeks against snapshot (frozen), not live now()
    snapshot_dt_naive = _dt.strptime(snapshot_str, '%Y-%m-%d %H:%M:%S')
    for r in stuck_rows:
        weeks = 0
        if r['first_c1_submitted']:
            try:
                sub_dt = _dt.fromisoformat(r['first_c1_submitted'].replace('Z', '+00:00') if 'Z' in r['first_c1_submitted'] else r['first_c1_submitted'])
                if sub_dt.tzinfo is not None:
                    sub_dt = sub_dt.replace(tzinfo=None)
                weeks = max(0, (snapshot_dt_naive - sub_dt).days // 7)
            except (ValueError, TypeError):
                weeks = 0"""

assert old_py in content, "ABORT: Change B old Python block did not match"
assert content.count(old_py) == 1, "ABORT: Change B old Python block matched multiple times"
content = content.replace(old_py, new_py)
print("OK Change B applied (Python: weeks calc anchored to snapshot)")

# ---------------------------------------------------------------------------
# Write back
# ---------------------------------------------------------------------------

TARGET.write_text(content)
print("DONE: wrote", TARGET)
