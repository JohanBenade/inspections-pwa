"""v321 patch — desnag_submit: ignore pending items with prior defects.

Root cause: `desnag_submit` counted every inspection_item row with status='pending'
as unaddressed, triggering abort(400) on submit. Per app workflow, items with prior
defects stay status='pending' after the defect is cleared via the defect-side UI;
this is intentional. The UI's progress widget (`_desnag_progress`) already filters
these out with `COALESCE(has_prior_defects, 0) = 0`. The submit check now does the same.

Affected: any C2+ unit where all prior defects have been addressed and only
cleared-prior items remain at status='pending'. e.g. units 008 and 010 in
batch 3237ea51 verified failing with this exact pattern.
"""
from pathlib import Path

p = Path('app/routes/inspection.py')
content = p.read_text()

OLD = '''    unaddressed_items = query_db("""
        SELECT COUNT(*) as cnt FROM inspection_item
        WHERE inspection_id = ? AND tenant_id = ? AND status = 'pending'
    """, [inspection_id, tenant_id], one=True)['cnt']'''

NEW = '''    unaddressed_items = query_db("""
        SELECT COUNT(*) as cnt FROM inspection_item
        WHERE inspection_id = ? AND tenant_id = ? AND status = 'pending'
        AND COALESCE(has_prior_defects, 0) = 0
    """, [inspection_id, tenant_id], one=True)['cnt']'''

n = content.count(OLD)
assert n == 1, f"Expected exactly 1 match for the original block, found {n}. File may have changed — abort."

content = content.replace(OLD, NEW)
p.write_text(content)
print("Patched: app/routes/inspection.py")
print("Added clause: AND COALESCE(has_prior_defects, 0) = 0")
print("Verify with: git diff app/routes/inspection.py")
