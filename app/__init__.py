"""
Inspections PWA - Flask Application Factory
Multi-tenant defect inspection for student housing
"""
import os
from flask import Flask, render_template, session, redirect, url_for, request

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', 'data/inspections.db')
    
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
        
        role = session.get('role', 'student')
        if role == 'architect':
            return redirect(url_for('cycles.list_cycles'))
        return redirect(url_for('projects.list_projects'))
    
    # Simple auth (magic link style - to be enhanced)
    @app.route('/login')
    def login():
        """Login via magic link parameter."""
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
        
        return render_template('login.html')
    
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
