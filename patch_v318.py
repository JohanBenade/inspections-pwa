"""
v318 - Apply active=1 filter to batches.py denominator queries (v317 Layer 2)

Adds WHERE active = 1 (or AND active = 1) to both item_template count queries
in batches.py, so the C1 denominator math (items_per_unit and ground_only_count)
reflects only active templates. Closes the v317 forward-correctness gap
identified in HANDOVER_v311 section 4.1.

Consumer trace (verified this session, 23 May 2026):
  - checkpoints_c1 set at batches.py lines 365, 595
  - read at batches.py lines 418, 643 to derive u['checkpoints']
  - u.checkpoints consumed only in app/templates/batches/_detail_tbody.html
    lines 29 and 32, gated to bu_status in ('in_progress', 'paused')
  - historical/closed units never render the num/den math => no over-complete
    artefact on already-certified inspections
"""

PATH = "app/routes/batches.py"

with open(PATH, "r") as f:
    content = f.read()

# Change 1: total_row query - add WHERE active = 1 (occurs twice, both blocks)
old_total = '"SELECT COUNT(*) AS cnt FROM item_template",'
new_total = '"SELECT COUNT(*) AS cnt FROM item_template WHERE active = 1",'
n_total = content.count(old_total)
assert n_total == 2, f"total_row: expected 2 matches, found {n_total}"
content = content.replace(old_total, new_total)

# Change 2: go_row query - add AND active = 1 (occurs twice, both blocks)
old_go = '''"SELECT COUNT(*) AS cnt FROM item_template WHERE floor_condition = 'ground_only'",'''
new_go = '''"SELECT COUNT(*) AS cnt FROM item_template WHERE floor_condition = 'ground_only' AND active = 1",'''
n_go = content.count(old_go)
assert n_go == 2, f"go_row: expected 2 matches, found {n_go}"
content = content.replace(old_go, new_go)

with open(PATH, "w") as f:
    f.write(content)

print(f"OK: v318 patched - {n_total} total_row + {n_go} go_row queries updated")
