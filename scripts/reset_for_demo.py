"""
Reset specific units for student demo.
Keeps 6 units with data (for Kevin demo), resets 2 to fresh state (for student demo).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.db import get_db


def main():
    app = create_app()
    
    with app.app_context():
        db = get_db()
        tenant_id = 'MONOGRAPH'
        
        # Get units to reset (last 2 units: B-1-102 and B-2-201)
        units_to_reset = db.execute("""
            SELECT id, block, floor, unit_number 
            FROM unit 
            WHERE tenant_id = ? 
            ORDER BY block DESC, floor DESC, unit_number DESC
            LIMIT 2
        """, [tenant_id]).fetchall()
        
        print("=== RESETTING UNITS FOR STUDENT DEMO ===")
        
        for unit in units_to_reset:
            unit_id = unit[0]
            unit_code = f"{unit[1]}-{unit[2]}-{unit[3]}"
            
            # Delete defects for this unit
            db.execute("DELETE FROM defect WHERE unit_id = ?", [unit_id])
            
            # Delete inspection items for inspections of this unit
            db.execute("""
                DELETE FROM inspection_item 
                WHERE inspection_id IN (SELECT id FROM inspection WHERE unit_id = ?)
            """, [unit_id])
            
            # Delete inspections for this unit
            db.execute("DELETE FROM inspection WHERE unit_id = ?", [unit_id])
            
            # Reset unit status
            db.execute("UPDATE unit SET status = 'not_started' WHERE id = ?", [unit_id])
            
            print(f"  Reset: {unit_code} -> not_started")
        
        db.commit()
        
        print()
        print("=== CURRENT UNIT STATUS ===")
        
        all_units = db.execute("""
            SELECT block || '-' || floor || '-' || unit_number AS code, status,
                   (SELECT COUNT(*) FROM defect WHERE unit_id = unit.id AND status = 'open') AS defects
            FROM unit
            WHERE tenant_id = ?
            ORDER BY block, floor, unit_number
        """, [tenant_id]).fetchall()
        
        for unit in all_units:
            print(f"  {unit[0]}: {unit[1]} ({unit[2]} open defects)")
        
        print()
        print("Done!")
        print("Student demo: B-1-102 and B-2-201 are fresh (not_started)")
        print("Kevin demo: Other 6 units have data")


if __name__ == '__main__':
    main()
