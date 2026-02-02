"""
Authentication decorators and utilities.
Centralized auth for all routes.

Role Hierarchy (highest to lowest):
- admin: Full access to everything
- manager: Approve, certify, close cycles, PDF
- team_lead: Create cycles, assign units, review, inspect
- inspector: Mark items, submit assigned units only
"""
from functools import wraps
from flask import session, redirect, url_for, abort


# Role hierarchy - higher index = more permissions
ROLE_HIERARCHY = {
    'inspector': 1,
    'team_lead': 2,
    'manager': 3,
    'admin': 4
}


def get_role_level(role):
    """Get numeric level for role comparison."""
    return ROLE_HIERARCHY.get(role, 0)


def require_auth(f):
    """Require any authenticated user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def require_role(minimum_role):
    """
    Decorator factory for role-based access.
    Usage: @require_role('team_lead')
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            
            user_role = session.get('role', 'inspector')
            if get_role_level(user_role) < get_role_level(minimum_role):
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_team_lead(f):
    """Require team_lead or higher (team_lead, manager, admin)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if get_role_level(session.get('role', 'inspector')) < get_role_level('team_lead'):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def require_manager(f):
    """Require manager or higher (manager, admin)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if get_role_level(session.get('role', 'inspector')) < get_role_level('manager'):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Require admin role only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """Get current user info from session."""
    if 'user_id' not in session:
        return None
    return {
        'id': session.get('user_id'),
        'name': session.get('user_name'),
        'role': session.get('role'),
        'tenant_id': session.get('tenant_id')
    }
