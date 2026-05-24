#!/usr/bin/env python3
"""
q_certified_v330.py - Verify v330 certified KPI math.

Replicates the queries in _build_pipeline_report_data() (live mode) to
verify the unified certified count on the pipeline dashboard.

Reports:
  - formal_certified  (unit.certified_at set)
  - handover_ready    (max inspection in reviewed-or-higher AND 0 open defects)
  - union             = formal | handover_ready  (the v330 KPI number)
  - overlap           = formal & handover_ready  (units in both)
  - formal_only       = formal - handover_ready
  - handover_only     = handover_ready - formal

Plus unit_number lists for each bucket.
"""

import sqlite3
from datetime import datetime

DB = '/var/data/inspections.db'
TENANT = 'MONOGRAPH'

now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# all_units - same as route (uses unit table with manual TEST filter)
all_units = conn.execute("""
    SELECT id, unit_number, certified_at
    FROM unit
    WHERE tenant_id = ? AND unit_number NOT LIKE 'TEST%'
""", [TENANT]).fetchall()

# unit_max_completed - same as route
completed_rows = conn.execute("""
    SELECT i.unit_id
    FROM inspection i
    JOIN unit_real u ON i.unit_id = u.id
    WHERE i.tenant_id = ? AND i.review_submitted_at <= ?
      AND i.status IN ('reviewed', 'approved', 'pending_followup')
    GROUP BY i.unit_id
""", [TENANT, now_str]).fetchall()
unit_max_completed = set(r['unit_id'] for r in completed_rows)

# unit_open - same as route (same filter, same EXISTS subquery)
open_rows = conn.execute("""
    SELECT d.unit_id, COUNT(*) AS cnt
    FROM defect d
    JOIN unit_real u ON d.unit_id = u.id
    WHERE d.tenant_id = ? AND d.created_at <= ?
      AND (d.status = 'open' OR (d.status = 'cleared' AND d.cleared_at > ?))
      AND d.raised_cycle_id NOT LIKE 'test-%'
      AND EXISTS (
        SELECT 1 FROM inspection i2
        WHERE i2.unit_id = d.unit_id
          AND i2.cycle_id = d.raised_cycle_id
          AND i2.status IN ('reviewed','approved','certified','pending_followup')
          AND i2.review_submitted_at <= ?
      )
    GROUP BY d.unit_id
""", [TENANT, now_str, now_str, now_str]).fetchall()
unit_open = {r['unit_id']: r['cnt'] for r in open_rows}

# Compute sets (mirror of v330 logic)
formal_set = set(u['id'] for u in all_units if u['certified_at'])
handover_set = set(uid for uid in unit_max_completed if unit_open.get(uid, 0) == 0)

union_set = formal_set | handover_set
overlap_set = formal_set & handover_set
formal_only = formal_set - handover_set
handover_only = handover_set - formal_set

# id -> unit_number for printing
id_to_unum = {u['id']: u['unit_number'] for u in all_units}

print("=" * 60)
print(f"v330 certified KPI verification (snapshot = {now_str} UTC)")
print("=" * 60)
print(f"formal_certified  (unit.certified_at set):           {len(formal_set):3d}")
print(f"handover_ready    (reviewed+ AND 0 open defects):    {len(handover_set):3d}")
print(f"UNION             (the v330 KPI number):             {len(union_set):3d}")
print(f"  overlap         (in both sets):                    {len(overlap_set):3d}")
print(f"  formal_only     (formal, not handover_ready):      {len(formal_only):3d}")
print(f"  handover_only   (handover_ready, not formal):      {len(handover_only):3d}")
print()
print("Unit numbers in each bucket:")
print(f"  overlap:       {sorted(id_to_unum[i] for i in overlap_set)}")
print(f"  formal_only:   {sorted(id_to_unum[i] for i in formal_only)}")
print(f"  handover_only: {sorted(id_to_unum[i] for i in handover_only)}")

conn.close()
print()
print("DONE")
