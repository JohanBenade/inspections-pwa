"""
Authentication decorators and utilities.
Centralized auth for all routes.
"""
from functools import wraps
from flask import session, redirect, url_for, abort


def require_auth(f):
    """Require any authenticated user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def require_architect(f):
    """Require architect role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'architect':
            abort(403)
        return f(*args, **kwargs)
    return decorated


def require_student(f):
    """Require student role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'student':
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
