"""
Inspections PWA - Flask Application Factory
Multi-tenant defect inspection for student housing
"""
import os
from datetime import timedelta
from flask import Flask, render_template, session, redirect, url_for, request

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', 'data/inspections.db')
    
    # PWA session persistence - 365 days
    app.permanent_session_lifetime = timedelta(days=365)
    
    @app.before_request
    def make_session_permanent():
        session.permanent = True
    
    # Initialize database
    from app.services.db import init_db
    with app.app_context():
        init_db(app)
    
    # Register blueprints
    from app.routes.projects import projects_bp
    from app.routes.inspection import inspection_bp
    from app.routes.defects import defects_bp
    from app.routes.certification import certification_bp
    from app.routes.cycles import cycles_bp
    
    app.register_blueprint(projects_bp)
    app.register_blueprint(inspection_bp)
    app.register_blueprint(defects_bp)
    app.register_blueprint(certification_bp)
    app.register_blueprint(cycles_bp)

    # Approvals blueprint (manager + admin)
    from app.routes.approvals import approvals_bp
    app.register_blueprint(approvals_bp)

    # Analytics blueprint (manager + admin only)
    from app.routes.analytics import analytics_bp
    app.register_blueprint(analytics_bp)

    # Data Quality blueprint (admin only)
    from app.routes.data_quality import data_quality_bp
    app.register_blueprint(data_quality_bp)
    
    # PDF blueprint (optional - requires weasyprint + system libs)
    try:
        from app.routes.pdf import pdf_bp
        app.register_blueprint(pdf_bp)
    except (ImportError, OSError):
        pass  # PDF generation not available
    
    # Home route
    @app.route('/')
    def home():
        """Landing page - role-based redirect."""
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        role = session.get('role', 'inspector')
        
        # Inspectors get their own home page with assigned units only
        if role == 'inspector':
            from app.services.db import query_db
            tenant_id = session['tenant_id']
            user_id = session['user_id']
            
            # Get inspections assigned to this inspector
            inspections = query_db("""
                SELECT i.id AS inspection_id, i.status AS inspection_status,
                       i.inspection_date, i.started_at, i.submitted_at,
                       u.unit_number, u.block, u.floor,
                       ic.cycle_number, ic.id AS cycle_id,
                       (SELECT COUNT(*) FROM inspection_item ii
                        WHERE ii.inspection_id = i.id
                        AND ii.status != 'skipped') AS total_items,
                       (SELECT COUNT(*) FROM inspection_item ii
                        WHERE ii.inspection_id = i.id
                        AND ii.status NOT IN ('skipped', 'pending')) AS completed_items,
                       (SELECT COUNT(*) FROM defect d
                        WHERE d.unit_id = u.id
                        AND d.raised_cycle_id = i.cycle_id
                        AND d.status = 'open') AS defect_count
                FROM inspection i
                JOIN unit u ON i.unit_id = u.id
                JOIN inspection_cycle ic ON i.cycle_id = ic.id
                WHERE i.inspector_id = ? AND i.tenant_id = ?
                AND i.status IN ('in_progress', 'submitted')
                ORDER BY
                    CASE i.status WHEN 'in_progress' THEN 0 ELSE 1 END,
                    u.unit_number
            """, [user_id, tenant_id])
            
            inspections = [dict(r) for r in inspections]
            return render_template('inspector_home.html', inspections=inspections)
        
        # All other roles go to cycles
        return redirect(url_for('cycles.list_cycles'))
    
    # Simple auth (magic link style - to be enhanced)
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Login via magic link parameter or login form."""
        user_code = None
        error = None

        if request.method == 'POST':
            user_code = request.form.get('code', '').strip()
        else:
            user_code = request.args.get('u')

        if user_code:
            from app.services.db import get_db
            db = get_db()
            user = db.execute(
                "SELECT * FROM inspector WHERE id = ? AND active = 1",
                [user_code]
            ).fetchone()
            
            if user:
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['role'] = user['role']
                session['tenant_id'] = user['tenant_id']
                return redirect(url_for('home'))
            else:
                error = 'Invalid login code. Please try again.'

        return render_template('login.html', error=error)
    
    @app.route('/logout')
    def logout():
        """Clear session."""
        session.clear()
        return redirect(url_for('login'))
    
    # Context processor for templates
    @app.context_processor
    def inject_user():
        from app.auth import get_current_user
        return {'current_user': get_current_user()}
    
    return app


# For direct execution
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
