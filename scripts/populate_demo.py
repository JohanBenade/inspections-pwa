"""
Populate Demo Data for Kevin Demo
Creates inspection data for all 8 units:
- 3 units: 100% clean, submitted, ready to certify
- 5 units: Random defects (10-15 per unit), submitted
"""
import sys
import os
import uuid
import random
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.db import get_db, query_db


def generate_id():
    """Generate short UUID."""
    return str(uuid.uuid4())[:8]


def get_all_items_for_unit(db, tenant_id, unit_type):
    """Get all item templates for a unit type with parent/child info."""
    items = db.execute("""
        SELECT 
            it.id,
            it.parent_item_id,
            it.item_description,
            ct.category_name,
            at.area_name
        FROM item_template it
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE at.tenant_id = ? AND at.unit_type = ?
        ORDER BY at.area_order, ct.category_order, it.item_order
    """, [tenant_id, unit_type]).fetchall()
    
    return items


def create_clean_inspection(db, tenant_id, unit, inspector_id, inspector_name):
    """Create a fully clean inspection - all items OK/Installed."""
    inspection_id = generate_id()
    
    db.execute("""
        INSERT INTO inspection (id, tenant_id, unit_id, round_number, round_type,
                               inspection_date, inspector_id, inspector_name, status,
                               submitted_at)
        VALUES (?, ?, ?, 1, 'initial', ?, ?, ?, 'submitted', CURRENT_TIMESTAMP)
    """, [inspection_id, tenant_id, unit['id'], date.today().isoformat(),
          inspector_id, inspector_name])
    
    items = get_all_items_for_unit(db, tenant_id, unit['unit_type'])
    
    # Build parent lookup
    parent_ids = set(item[1] for item in items if item[1])
    
    for item in items:
        item_id = item[0]
        parent_item_id = item[1]
        is_parent = item_id in parent_ids
        
        if is_parent:
            status = 'installed'
        else:
            status = 'ok'
        
        db.execute("""
            INSERT INTO inspection_item (id, tenant_id, inspection_id, item_template_id, status)
            VALUES (?, ?, ?, ?, ?)
        """, [generate_id(), tenant_id, inspection_id, item_id, status])
    
    # Update unit status to cleared (ready to certify)
    db.execute("UPDATE unit SET status = 'cleared' WHERE id = ?", [unit['id']])
    
    return inspection_id


def create_defect_inspection(db, tenant_id, unit, inspector_id, inspector_name, num_defects):
    """Create an inspection with random defects."""
    inspection_id = generate_id()
    
    db.execute("""
        INSERT INTO inspection (id, tenant_id, unit_id, round_number, round_type,
                               inspection_date, inspector_id, inspector_name, status,
                               submitted_at)
        VALUES (?, ?, ?, 1, 'initial', ?, ?, ?, 'submitted', CURRENT_TIMESTAMP)
    """, [inspection_id, tenant_id, unit['id'], date.today().isoformat(),
          inspector_id, inspector_name])
    
    items = get_all_items_for_unit(db, tenant_id, unit['unit_type'])
    
    # Build parent lookup
    parent_ids = set(item[1] for item in items if item[1])
    item_list = list(items)
    
    # Separate parents and children/standalone
    parents = [i for i in item_list if i[0] in parent_ids]
    children_standalone = [i for i in item_list if i[0] not in parent_ids]
    
    # Select defects: mix of parent not_installed and child defects
    num_parent_defects = random.randint(2, 4)
    num_child_defects = num_defects - num_parent_defects
    
    defect_parents = set(random.sample([p[0] for p in parents], min(num_parent_defects, len(parents))))
    
    # Get children that don't belong to defect parents (those will be greyed out)
    available_children = [c for c in children_standalone if c[1] not in defect_parents]
    defect_children = set(random.sample([c[0] for c in available_children], 
                                        min(num_child_defects, len(available_children))))
    
    defect_comments = [
        "Paint scratched",
        "Not level",
        "Gap visible",
        "Crack in finish",
        "Missing sealant",
        "Poor alignment",
        "Surface damage",
        "Incomplete installation",
        "Wrong color",
        "Needs touch-up",
        "Chip in corner",
        "Stain visible",
        "Not flush",
        "Loose fitting",
        "Scuff marks"
    ]
    
    for item in item_list:
        item_id = item[0]
        parent_item_id = item[1]
        is_parent = item_id in parent_ids
        
        if is_parent:
            if item_id in defect_parents:
                status = 'not_installed'
                comment = "Not installed - missing from unit"
            else:
                status = 'installed'
                comment = None
        else:
            # Child or standalone
            if parent_item_id in defect_parents:
                # Parent not installed - child should be pending (greyed out)
                status = 'pending'
                comment = None
            elif item_id in defect_children:
                status = random.choice(['not_to_standard', 'not_installed'])
                comment = random.choice(defect_comments)
            else:
                status = 'ok'
                comment = None
        
        db.execute("""
            INSERT INTO inspection_item (id, tenant_id, inspection_id, item_template_id, status, comment)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [generate_id(), tenant_id, inspection_id, item_id, status, comment])
        
        # Create defect record for defective items
        if status in ['not_to_standard', 'not_installed'] and comment:
            defect_id = generate_id()
            db.execute("""
                INSERT INTO defect (id, tenant_id, unit_id, item_template_id,
                                   raised_inspection_id, raised_round, defect_type,
                                   original_comment, status)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, 'open')
            """, [defect_id, tenant_id, unit['id'], item_id, inspection_id, status, comment])
    
    # Update unit status
    db.execute("UPDATE unit SET status = 'defects_open' WHERE id = ?", [unit['id']])
    
    return inspection_id


def main():
    app = create_app()
    
    with app.app_context():
        db = get_db()
        tenant_id = 'MONOGRAPH'
        
        # Clear existing inspection data
        db.execute("DELETE FROM defect")
        db.execute("DELETE FROM inspection_item")
        db.execute("DELETE FROM inspection")
        db.execute("UPDATE unit SET status = 'not_started'")
        
        # Get inspector
        inspector = db.execute(
            "SELECT * FROM inspector WHERE tenant_id = ? AND role = 'student' LIMIT 1",
            [tenant_id]
        ).fetchone()
        
        if not inspector:
            print("No student inspector found!")
            return
        
        inspector_id = inspector[0]
        inspector_name = inspector[2]
        
        # Get all units
        units = db.execute(
            "SELECT * FROM unit WHERE tenant_id = ? ORDER BY block, floor, unit_number",
            [tenant_id]
        ).fetchall()
        
        if len(units) < 8:
            print(f"Only {len(units)} units found, expected 8")
            return
        
        # Convert to dict-like access
        unit_dicts = []
        for u in units:
            unit_dicts.append({
                'id': u[0],
                'tenant_id': u[1],
                'phase_id': u[2],
                'block': u[3],
                'floor': u[4],
                'unit_number': u[5],
                'unit_type': u[6],
                'status': u[7]
            })
        
        print(f"Processing {len(unit_dicts)} units...")
        print(f"Inspector: {inspector_name} ({inspector_id})")
        print()
        
        # 3 clean units (first 3)
        clean_units = unit_dicts[:3]
        # 5 defect units (remaining)
        defect_units = unit_dicts[3:]
        
        print("=== CLEAN UNITS (Ready to Certify) ===")
        for unit in clean_units:
            unit_code = f"{unit['block']}-{unit['floor']}-{unit['unit_number']}"
            inspection_id = create_clean_inspection(db, tenant_id, unit, inspector_id, inspector_name)
            print(f"  {unit_code}: All items OK - status = cleared")
        
        print()
        print("=== DEFECT UNITS ===")
        for unit in defect_units:
            unit_code = f"{unit['block']}-{unit['floor']}-{unit['unit_number']}"
            num_defects = random.randint(10, 15)
            inspection_id = create_defect_inspection(db, tenant_id, unit, inspector_id, inspector_name, num_defects)
            
            # Count actual defects created
            defect_count = db.execute(
                "SELECT COUNT(*) FROM defect WHERE unit_id = ?", [unit['id']]
            ).fetchone()[0]
            
            print(f"  {unit_code}: {defect_count} defects - status = defects_open")
        
        db.commit()
        
        print()
        print("=== SUMMARY ===")
        
        # Summary by status
        for status in ['not_started', 'in_progress', 'cleared', 'defects_open', 'certified']:
            count = db.execute(
                "SELECT COUNT(*) FROM unit WHERE tenant_id = ? AND status = ?",
                [tenant_id, status]
            ).fetchone()[0]
            if count > 0:
                print(f"  {status}: {count} units")
        
        total_defects = db.execute(
            "SELECT COUNT(*) FROM defect WHERE tenant_id = ?", [tenant_id]
        ).fetchone()[0]
        print(f"  Total open defects: {total_defects}")
        
        print()
        print("Done! Demo data created.")


if __name__ == '__main__':
    main()
