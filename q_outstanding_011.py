import sqlite3
c = sqlite3.connect('/var/data/inspections.db')
c.row_factory = sqlite3.Row
cur = c.cursor()

rows = cur.execute("""
    SELECT
        at2.area_order AS ao, ct.category_order AS co, it.item_order AS io,
        1 AS action_type,
        at2.area_name AS area, ct.category_name AS cat,
        it.item_description AS item, par.item_description AS parent,
        'Clear/Still-Open' AS action,
        d.original_comment AS detail
    FROM defect d
    JOIN item_template it ON d.item_template_id = it.id
    LEFT JOIN item_template par ON it.parent_item_id = par.id
    JOIN category_template ct ON it.category_id = ct.id
    JOIN area_template at2 ON ct.area_id = at2.id
    WHERE d.unit_id = '37abd384'
      AND d.status = 'open'
      AND d.addressed_cycle_number IS NULL
      AND d.raised_cycle_number < 2

    UNION ALL

    SELECT
        at2.area_order AS ao, ct.category_order AS co, it.item_order AS io,
        2 AS action_type,
        at2.area_name AS area, ct.category_name AS cat,
        it.item_description AS item, par.item_description AS parent,
        'MS/NTS (item)' AS action,
        '-' AS detail
    FROM inspection_item ii
    JOIN item_template it ON ii.item_template_id = it.id
    LEFT JOIN item_template par ON it.parent_item_id = par.id
    JOIN category_template ct ON it.category_id = ct.id
    JOIN area_template at2 ON ct.area_id = at2.id
    WHERE ii.inspection_id = '1f666236' AND ii.status = 'pending'

    ORDER BY ao, co, io, action_type
""").fetchall()

print(f"\n{'#':<3} {'AREA':<13} {'CATEGORY':<14} {'ITEM':<28} {'ACTION':<18} {'DETAIL'}")
print('-' * 110)
for n, r in enumerate(rows, 1):
    item = (r['item'] or '')[:27]
    if r['parent']:
        item = '> ' + item[:25]
    print(f"{n:<3} {(r['area'] or '')[:12]:<13}{(r['cat'] or '')[:13]:<14}{item:<28} {r['action']:<18} {(r['detail'] or '-')[:50]}")
print(f"\nTotal: {len(rows)} outstanding actions")
c.close()
