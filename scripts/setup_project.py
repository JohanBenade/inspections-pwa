"""
Setup Project - Configure project, phase, units and inspectors from JSON config.

Usage:
    python scripts/setup_project.py                    # Uses default config/soshanguve.json
    python scripts/setup_project.py config/other.json # Uses specified config file

Config file structure:
{
    "tenant": {"id": "...", "name": "..."},
    "project": {"id": "...", "name": "...", "code": "...", "client": "..."},
    "phase": {"id": "...", "name": "...", "code": "..."},
    "units": [{"block": "A", "floor": 1, "start": 101, "count": 3, "type": "4-Bed"}, ...],
    "inspectors": [{"id": "...", "name": "...", "email": "...", "role": "..."}, ...]
}
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.db import get_db, query_db


def load_config(config_path):
    """Load project configuration from JSON file."""
    with open(config_path, 'r') as f:
        return json.load(f)


def setup_inspectors(db, config):
    """Create inspector accounts."""
    tenant_id = config['tenant']['id']
    
    for inspector in config['inspectors']:
        existing = db.execute(
            "SELECT id FROM inspector WHERE id = ?", [inspector['id']]
        ).fetchone()
        
        if not existing:
            db.execute("""
                INSERT INTO inspector (id, tenant_id, name, email, role)
                VALUES (?, ?, ?, ?, ?)
            """, [
                inspector['id'],
                tenant_id,
                inspector['name'],
                inspector.get('email', ''),
                inspector['role']
            ])
            print(f"  Created inspector: {inspector['name']} ({inspector['role']})")
        else:
            # Update existing
            db.execute("""
                UPDATE inspector SET name = ?, email = ?, role = ?
                WHERE id = ?
            """, [
                inspector['name'],
                inspector.get('email', ''),
                inspector['role'],
                inspector['id']
            ])
            print(f"  Updated inspector: {inspector['name']} ({inspector['role']})")


def setup_project(db, config):
    """Create or update project."""
    tenant_id = config['tenant']['id']
    project = config['project']
    
    existing = db.execute(
        "SELECT id FROM project WHERE id = ?", [project['id']]
    ).fetchone()
    
    if not existing:
        db.execute("""
            INSERT INTO project (id, tenant_id, project_name, client_name, project_code)
            VALUES (?, ?, ?, ?, ?)
        """, [
            project['id'],
            tenant_id,
            project['name'],
            project['client'],
            project['code']
        ])
        print(f"  Created project: {project['name']} ({project['code']})")
    else:
        db.execute("""
            UPDATE project SET project_name = ?, client_name = ?, project_code = ?
            WHERE id = ?
        """, [project['name'], project['client'], project['code'], project['id']])
        print(f"  Updated project: {project['name']} ({project['code']})")


def setup_phase(db, config):
    """Create or update phase."""
    tenant_id = config['tenant']['id']
    project_id = config['project']['id']
    phase = config['phase']
    
    existing = db.execute(
        "SELECT id FROM phase WHERE id = ?", [phase['id']]
    ).fetchone()
    
    if not existing:
        db.execute("""
            INSERT INTO phase (id, tenant_id, project_id, phase_name, phase_code)
            VALUES (?, ?, ?, ?, ?)
        """, [
            phase['id'],
            tenant_id,
            project_id,
            phase['name'],
            phase['code']
        ])
        print(f"  Created phase: {phase['name']} ({phase['code']})")
    else:
        db.execute("""
            UPDATE phase SET phase_name = ?, phase_code = ?
            WHERE id = ?
        """, [phase['name'], phase['code'], phase['id']])
        print(f"  Updated phase: {phase['name']} ({phase['code']})")


def setup_units(db, config):
    """Create units from config."""
    tenant_id = config['tenant']['id']
    phase_id = config['phase']['id']
    
    # Clear existing units for this phase (and related data)
    existing_units = db.execute(
        "SELECT id FROM unit WHERE phase_id = ?", [phase_id]
    ).fetchall()
    
    if existing_units:
        unit_ids = [u[0] for u in existing_units]
        # Clear ALL inspection data for these units (correct FK order)
        for unit_id in unit_ids:
            # Delete category comments and history
            db.execute("""
                DELETE FROM category_comment_history WHERE category_comment_id IN
                (SELECT id FROM category_comment WHERE unit_id = ?)
            """, [unit_id])
            db.execute("DELETE FROM category_comment WHERE unit_id = ?", [unit_id])
            
            # Delete defect history then defects
            db.execute("""
                DELETE FROM defect_history WHERE defect_id IN
                (SELECT id FROM defect WHERE unit_id = ?)
            """, [unit_id])
            db.execute("DELETE FROM defect WHERE unit_id = ?", [unit_id])
            
            # Delete inspection items then inspections
            db.execute("""
                DELETE FROM inspection_item WHERE inspection_id IN 
                (SELECT id FROM inspection WHERE unit_id = ?)
            """, [unit_id])
            db.execute("DELETE FROM inspection WHERE unit_id = ?", [unit_id])
        
        # Now delete units
        db.execute("DELETE FROM unit WHERE phase_id = ?", [phase_id])
        print(f"  Cleared {len(existing_units)} existing units")
    
    # Also clear any cycles for this phase (they reference units indirectly)
    db.execute("""
        DELETE FROM cycle_excluded_item WHERE cycle_id IN
        (SELECT id FROM inspection_cycle WHERE phase_id = ?)
    """, [phase_id])
    db.execute("DELETE FROM inspection_cycle WHERE phase_id = ?", [phase_id])
    
    # Create new units
    unit_count = 0
    unit_num = 1
    
    for unit_spec in config['units']:
        block = unit_spec.get('block', '')
        floor = unit_spec.get('floor', 0)
        unit_type = unit_spec['type']
        
        # Support both formats: individual units or ranges
        if 'number' in unit_spec:
            # Individual unit
            unit_number = unit_spec['number']
            unit_id = f"unit-{unit_num:03d}"
            
            db.execute("""
                INSERT INTO unit (id, tenant_id, phase_id, block, floor, unit_number, unit_type, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'not_started')
            """, [unit_id, tenant_id, phase_id, block, floor, unit_number, unit_type])
            
            unit_count += 1
            unit_num += 1
        else:
            # Range of units
            start = unit_spec['start']
            count = unit_spec['count']
            
            for i in range(count):
                unit_number = str(start + i)
                unit_id = f"unit-{unit_num:03d}"
                
                db.execute("""
                    INSERT INTO unit (id, tenant_id, phase_id, block, floor, unit_number, unit_type, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'not_started')
                """, [unit_id, tenant_id, phase_id, block, floor, unit_number, unit_type])
                
                unit_count += 1
                unit_num += 1
    
    print(f"  Created {unit_count} units")


def main():
    # Determine config file
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config', 'powerpark.json'
        )
    
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    print(f"Loading config: {config_path}")
    config = load_config(config_path)
    
    print(f"\n=== Setting up: {config['project']['name']} ===\n")
    
    app = create_app()
    
    with app.app_context():
        db = get_db()
        
        print(f"Tenant: {config['tenant']['name']} ({config['tenant']['id']})")
        
        print("\nInspectors:")
        setup_inspectors(db, config)
        
        print("\nProject:")
        setup_project(db, config)
        
        print("\nPhase:")
        setup_phase(db, config)
        
        print("\nUnits:")
        setup_units(db, config)
        
        db.commit()
        
        print("\n=== Setup Complete ===")
        print(f"\nLogin URLs:")
        for inspector in config['inspectors']:
            print(f"  {inspector['name']}: http://127.0.0.1:5000/login?u={inspector['id']}")


if __name__ == '__main__':
    main()
