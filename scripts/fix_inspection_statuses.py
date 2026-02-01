"""
Fix inspection_item statuses from defect table.
For Unit 027, sync status from defects.
"""
import sqlite3
import os

DB_PATH = os.environ.get('DATABASE_PATH', '/var/data/inspections.db')

def fix_statuses():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get inspection for Unit 027
    cur.execute("""
        SELECT i.id as inspection_id, i.unit_id
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        WHERE u.unit_number = '027'
    """)
    inspection = cur.fetchone()
    
    if not inspection:
        print("No inspection found for Unit 027")
        return
    
    print(f"Inspection ID: {inspection['inspection_id']}")
    print(f"Unit ID: {inspection['unit_id']}")
    
    # Get open defects for this unit
    cur.execute("""
        SELECT d.item_template_id, d.defect_type, d.original_comment
        FROM defect d
        WHERE d.unit_id = ? AND d.status = 'open'
    """, [inspection['unit_id']])
    defects = cur.fetchall()
    
    print(f"\nFound {len(defects)} open defects")
    
    # Check current status before fix
    cur.execute("""
        SELECT status, COUNT(*) as cnt
        FROM inspection_item
        WHERE inspection_id = ?
        GROUP BY status
    """, [inspection['inspection_id']])
    print("\nBEFORE fix:")
    for row in cur.fetchall():
        print(f"  {row['status']}: {row['cnt']}")
    
    # Update inspection_item status for each defect
    updated = 0
    for defect in defects:
        status = defect['defect_type']  # 'not_to_standard' or 'not_installed'
        comment = defect['original_comment']
        
        cur.execute("""
            UPDATE inspection_item
            SET status = ?, comment = ?
            WHERE inspection_id = ? AND item_template_id = ?
        """, [status, comment, inspection['inspection_id'], defect['item_template_id']])
        
        if cur.rowcount > 0:
            updated += 1
    
    conn.commit()
    print(f"\nUpdated {updated} inspection items")
    
    # Check status after fix
    cur.execute("""
        SELECT status, COUNT(*) as cnt
        FROM inspection_item
        WHERE inspection_id = ?
        GROUP BY status
    """, [inspection['inspection_id']])
    print("\nAFTER fix:")
    for row in cur.fetchall():
        print(f"  {row['status']}: {row['cnt']}")
    
    conn.close()
    print("\nDone!")

if __name__ == '__main__':
    fix_statuses()
