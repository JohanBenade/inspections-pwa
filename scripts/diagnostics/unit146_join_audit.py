"""
Check whether the bfwd_open INNER JOIN chain (item_template, category_template,
area_template) silently drops any of unit 146's 144 open prior defects.

If bfwd_open returns < 144, we've found the bug: defects with broken FK chains
(NULL category_id on child item_template, etc.) are excluded from the Defects
sub-section, so they only appear as 'Defects Remain' in the Items-to-Inspect section.
"""
import sqlite3

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

UID = 'd41d75d0'
TEN = 'MONOGRAPH'

# 1. Total open prior defects (unfiltered)
total = cur.execute(
    "SELECT COUNT(*) AS n FROM defect "
    "WHERE unit_id = ? AND tenant_id = ? "
    "AND status = 'open' AND raised_cycle_number < 2",
    (UID, TEN)
).fetchone()['n']
print(f'Total open prior defects (no joins): {total}')

# 2. Mirror of bfwd_open (INNER JOINs as at L2177)
inner = cur.execute(
    "SELECT COUNT(*) AS n FROM defect d "
    "JOIN item_template it ON d.item_template_id = it.id "
    "JOIN category_template ct ON it.category_id = ct.id "
    "JOIN area_template at2 ON ct.area_id = at2.id "
    "WHERE d.unit_id = ? AND d.tenant_id = ? "
    "  AND d.status = 'open' AND d.raised_cycle_number < 2",
    (UID, TEN)
).fetchone()['n']
print(f'bfwd_open mirror (INNER JOINs):     {inner}')
print(f'DROPPED by JOINs:                   {total - inner}')

# 3. Use LEFT JOINs to find which JOIN drops them
print('\n=== LEFT JOIN audit (where each NULL appears) ===')
results = cur.execute(
    "SELECT d.id AS defect_id, d.item_template_id, "
    "       it.id AS it_id, it.item_description, it.category_id, it.parent_item_id, "
    "       ct.id AS ct_id, ct.category_name, "
    "       at2.id AS area_id, at2.area_name "
    "FROM defect d "
    "LEFT JOIN item_template it ON d.item_template_id = it.id "
    "LEFT JOIN category_template ct ON it.category_id = ct.id "
    "LEFT JOIN area_template at2 ON ct.area_id = at2.id "
    "WHERE d.unit_id = ? AND d.tenant_id = ? "
    "  AND d.status = 'open' AND d.raised_cycle_number < 2",
    (UID, TEN)
).fetchall()

null_it = [r for r in results if r['it_id'] is None]
null_cat = [r for r in results if r['it_id'] is not None and r['ct_id'] is None]
null_area = [r for r in results if r['ct_id'] is not None and r['area_id'] is None]
ok = [r for r in results if r['area_id'] is not None]

print(f'NULL item_template:  {len(null_it)}')
print(f'NULL category:       {len(null_cat)}')
print(f'NULL area:           {len(null_area)}')
print(f'All joins OK:        {len(ok)}')

# Show samples of dropped defects
if null_cat:
    print('\n--- sample defects dropped at category join ---')
    for r in null_cat[:5]:
        print(' ', dict(r))
if null_area:
    print('\n--- sample defects dropped at area join ---')
    for r in null_area[:5]:
        print(' ', dict(r))

# 4. Group bfwd_open by area+category to see distribution
print('\n=== bfwd_open distribution by area+category ===')
for r in cur.execute(
    "SELECT at2.area_name, ct.category_name, COUNT(*) AS n "
    "FROM defect d "
    "JOIN item_template it ON d.item_template_id = it.id "
    "JOIN category_template ct ON it.category_id = ct.id "
    "JOIN area_template at2 ON ct.area_id = at2.id "
    "WHERE d.unit_id = ? AND d.tenant_id = ? "
    "  AND d.status = 'open' AND d.raised_cycle_number < 2 "
    "GROUP BY at2.area_name, ct.category_name "
    "ORDER BY at2.area_order, ct.category_order",
    (UID, TEN)
).fetchall():
    print(f"  {r['area_name']:20s}  {r['category_name']:30s}  {r['n']}")

conn.close()
