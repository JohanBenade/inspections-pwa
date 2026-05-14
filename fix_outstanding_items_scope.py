#!/usr/bin/env python3
"""
Outstanding Items List patches:
  1. Filter both queries to units with at least one C2+ inspection on record
     (EXISTS clause on inspection table).
  2. LEFT JOIN to parent item_template so sub-items sort under their parent.
  3. Revised ORDER BY: block, floor, unit, area, category, parent_item_order,
     depth, item_order (handles root + subitem hierarchy).
"""
from pathlib import Path

ANALYTICS = Path("app/routes/analytics.py")
assert ANALYTICS.exists()

OLD = """    try:
        defect_rows = conn.execute(\"\"\"
            SELECT u.block, u.floor, u.unit_number,
                   at.area_name, at.area_order,
                   ct.category_name AS trade, ct.category_order,
                   it.item_description, it.item_order,
                   COALESCE(NULLIF(d.reviewed_comment,''), NULLIF(d.raw_comment,''), d.original_comment) AS description,
                   d.raised_cycle_number, d.created_at
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id AND it.tenant_id = d.tenant_id
            JOIN category_template ct ON it.category_id = ct.id AND ct.tenant_id = d.tenant_id
            JOIN area_template at ON ct.area_id = at.id AND at.tenant_id = d.tenant_id
            JOIN unit_real u ON d.unit_id = u.id AND u.tenant_id = d.tenant_id
            WHERE d.tenant_id = ? AND d.status = 'open'
            ORDER BY u.block, u.floor, CAST(u.unit_number AS INTEGER),
                     at.area_order, ct.category_order, it.item_order
        \"\"\", (tenant_id,)).fetchall()

        latent_rows = conn.execute(\"\"\"
            SELECT u.block, u.floor, u.unit_number,
                   at.area_name, at.area_order,
                   lan.note_html, lan.cycle_number, lan.created_at
            FROM latent_area_note lan
            JOIN area_template at ON lan.area_template_id = at.id AND at.tenant_id = lan.tenant_id
            JOIN unit_real u ON lan.unit_id = u.id AND u.tenant_id = lan.tenant_id
            WHERE lan.tenant_id = ? AND lan.rectified_at IS NULL
            ORDER BY u.block, u.floor, CAST(u.unit_number AS INTEGER), at.area_order
        \"\"\", (tenant_id,)).fetchall()
    finally:
        conn.close()"""

NEW = """    try:
        defect_rows = conn.execute(\"\"\"
            SELECT u.block, u.floor, u.unit_number,
                   at.area_name, at.area_order,
                   ct.category_name AS trade, ct.category_order,
                   it.item_description, it.item_order, it.depth,
                   COALESCE(pit.item_order, it.item_order) AS sort_parent,
                   COALESCE(NULLIF(d.reviewed_comment,''), NULLIF(d.raw_comment,''), d.original_comment) AS description,
                   d.raised_cycle_number, d.created_at
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id AND it.tenant_id = d.tenant_id
            LEFT JOIN item_template pit ON it.parent_item_id = pit.id AND pit.tenant_id = it.tenant_id
            JOIN category_template ct ON it.category_id = ct.id AND ct.tenant_id = d.tenant_id
            JOIN area_template at ON ct.area_id = at.id AND at.tenant_id = d.tenant_id
            JOIN unit_real u ON d.unit_id = u.id AND u.tenant_id = d.tenant_id
            WHERE d.tenant_id = ? AND d.status = 'open'
              AND EXISTS (
                  SELECT 1 FROM inspection i
                  WHERE i.unit_id = d.unit_id
                    AND i.tenant_id = d.tenant_id
                    AND i.cycle_number >= 2
              )
            ORDER BY u.block, u.floor, CAST(u.unit_number AS INTEGER),
                     at.area_order, ct.category_order,
                     sort_parent, it.depth, it.item_order
        \"\"\", (tenant_id,)).fetchall()

        latent_rows = conn.execute(\"\"\"
            SELECT u.block, u.floor, u.unit_number,
                   at.area_name, at.area_order,
                   lan.note_html, lan.cycle_number, lan.created_at
            FROM latent_area_note lan
            JOIN area_template at ON lan.area_template_id = at.id AND at.tenant_id = lan.tenant_id
            JOIN unit_real u ON lan.unit_id = u.id AND u.tenant_id = lan.tenant_id
            WHERE lan.tenant_id = ? AND lan.rectified_at IS NULL
              AND EXISTS (
                  SELECT 1 FROM inspection i
                  WHERE i.unit_id = lan.unit_id
                    AND i.tenant_id = lan.tenant_id
                    AND i.cycle_number >= 2
              )
            ORDER BY u.block, u.floor, CAST(u.unit_number AS INTEGER), at.area_order
        \"\"\", (tenant_id,)).fetchall()
    finally:
        conn.close()"""


def main():
    src = ANALYTICS.read_text()

    if 'i.cycle_number >= 2' in src and 'sort_parent' in src:
        print('[NO-OP] C2+ filter and subitem sort already applied.')
        raise SystemExit(0)

    assert OLD in src, 'Anchor missing - drift'
    assert src.count(OLD) == 1, 'Anchor not unique'

    new_src = src.replace(OLD, NEW)

    assert 'i.cycle_number >= 2' in new_src
    assert 'sort_parent, it.depth, it.item_order' in new_src
    assert 'LEFT JOIN item_template pit' in new_src
    # Both queries got the EXISTS clause:
    assert new_src.count('AND i.cycle_number >= 2') == 2

    ANALYTICS.write_text(new_src)
    print('[OK] C2+ unit filter added (both queries). Subitem sort order added.')


if __name__ == '__main__':
    main()
