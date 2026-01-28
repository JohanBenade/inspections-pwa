"""
Update project/phase name without wiping inspection data.
Run after extracting new zip to rename project.

Usage:
    python scripts/rename_project.py
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
        
        # Update project name
        db.execute("""
            UPDATE project 
            SET project_name = 'Power Park Student Housing',
                project_code = 'PPSH'
            WHERE tenant_id = 'MONOGRAPH'
        """)
        
        # Update phase name
        db.execute("""
            UPDATE phase 
            SET phase_name = 'Phase 3',
                phase_code = 'PH3'
            WHERE tenant_id = 'MONOGRAPH'
        """)
        
        db.commit()
        
        print("Updated:")
        print("  Project: Power Park Student Housing")
        print("  Phase: Phase 3")
        print("\nInspection data preserved.")

if __name__ == '__main__':
    main()
