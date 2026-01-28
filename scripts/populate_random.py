#!/usr/bin/env python3
"""
Populate all units with inspections and random item statuses.
Run from inspections-pwa directory: python3 scripts/populate_random.py
"""
import random
import uuid
from datetime import date

def generate_id():
    return str(uuid.uuid4())[:8]

def main():
    import sqlite3
    conn = sqlite3.connect('data/inspections.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get all units
    units = cur.execute("""
        SELECT u.id, u.tenant_id, u.unit_type, 
               u.block || '-' || u.floor || '-' || u.unit_number as unit_code
        FROM unit u
    """).fetchall()
    
    print(f"Found {len(units)} units")
    
    defect_counter = 0
    total_items = 0
    total_defects = 0
    
    for unit in units:
        print(f"\nProcessing {unit['unit_code']}...")
        
        # Create inspection
        inspection_id = generate_id()
        cur.execute("""
            INSERT INTO inspection (id, tenant_id, unit_id, round_number, round_type,
                                   inspection_date, inspector_id, inspector_name, status)
            VALUES (?, ?, ?, 1, 'initial', ?, 'insp-001', 'Student One', 'in_progress')
        """, [inspection_id, unit['tenant_id'], unit['id'], date.today().isoformat()])
        
        # Get all items with parent info
        items = cur.execute("""
            SELECT it.id, it.parent_item_id,
                   EXISTS(SELECT 1 FROM item_template child WHERE child.parent_item_id = it.id) as is_parent
            FROM item_template it
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at ON ct.area_id = at.id
            WHERE at.tenant_id = ? AND at.unit_type = ?
        """, [unit['tenant_id'], unit['unit_type']]).fetchall()
        
        # Build parent status map
        parent_status = {}
        unit_defects = 0
        
        # First pass: mark parent items
        for item in items:
            if item['is_parent']:
                # Parent: 80% installed, 20% not installed
                if random.random() < 0.80:
                    status = 'installed'
                else:
                    status = 'not_installed'
                    defect_counter += 1
                    unit_defects += 1
                
                parent_status[item['id']] = status
                
                item_id = generate_id()
                cur.execute("""
                    INSERT INTO inspection_item (id, tenant_id, inspection_id, item_template_id, status, comment)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, [item_id, unit['tenant_id'], inspection_id, item['id'], status, 
                      f"defect {defect_counter}" if status == 'not_installed' else None])
                
                # Create defect for not installed parent
                if status == 'not_installed':
                    defect_id = generate_id()
                    cur.execute("""
                        INSERT INTO defect (id, tenant_id, unit_id, item_template_id, raised_inspection_id,
                                           raised_round, defect_type, original_comment, status)
                        VALUES (?, ?, ?, ?, ?, 1, 'not_installed', ?, 'open')
                    """, [defect_id, unit['tenant_id'], unit['id'], item['id'], 
                          inspection_id, f"defect {defect_counter}"])
                
                total_items += 1
        
        # Second pass: mark child/standalone items
        for item in items:
            if not item['is_parent']:
                parent_id = item['parent_item_id']
                
                # Skip if parent is not installed
                if parent_id and parent_status.get(parent_id) == 'not_installed':
                    # Still create the record but mark as pending (greyed out)
                    item_id = generate_id()
                    cur.execute("""
                        INSERT INTO inspection_item (id, tenant_id, inspection_id, item_template_id, status)
                        VALUES (?, ?, ?, ?, 'pending')
                    """, [item_id, unit['tenant_id'], inspection_id, item['id']])
                    total_items += 1
                    continue
                
                # Random status: 70% OK, 15% NTS, 10% N/I, 5% N/A
                rand = random.random()
                if rand < 0.70:
                    status = 'ok'
                    comment = None
                elif rand < 0.85:
                    status = 'not_to_standard'
                    defect_counter += 1
                    comment = f"defect {defect_counter}"
                    unit_defects += 1
                elif rand < 0.95:
                    status = 'not_installed'
                    defect_counter += 1
                    comment = f"defect {defect_counter}"
                    unit_defects += 1
                else:
                    status = 'not_applicable'
                    comment = None
                
                item_id = generate_id()
                cur.execute("""
                    INSERT INTO inspection_item (id, tenant_id, inspection_id, item_template_id, status, comment)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, [item_id, unit['tenant_id'], inspection_id, item['id'], status, comment])
                
                # Create defect record if NTS or N/I
                if status in ('not_to_standard', 'not_installed'):
                    defect_id = generate_id()
                    cur.execute("""
                        INSERT INTO defect (id, tenant_id, unit_id, item_template_id, raised_inspection_id,
                                           raised_round, defect_type, original_comment, status)
                        VALUES (?, ?, ?, ?, ?, 1, ?, ?, 'open')
                    """, [defect_id, unit['tenant_id'], unit['id'], item['id'], 
                          inspection_id, status, comment])
                
                total_items += 1
        
        total_defects += unit_defects
        
        # Mark inspection as submitted
        cur.execute("""
            UPDATE inspection SET status = 'submitted' WHERE id = ?
        """, [inspection_id])
        
        print(f"  Created {total_items} items, {unit_defects} defects")
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*50}")
    print(f"DONE: {len(units)} units, {total_items} total items, {total_defects} defects")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
