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


def can_edit_inspection(inspection_status, user_role):
    """
    Determine if user can edit an inspection based on status and role.
    
    Locking rules:
    - inspector: can only edit when status is 'in_progress' or None
    - team_lead: can edit 'in_progress' or 'submitted'
    - manager/admin: can edit anything except terminal states
    - Terminal states (locked for everyone): closed, certified, pending_followup
    
    Returns: (can_edit: bool, reason: str or None)
    """
    if inspection_status is None:
        return True, None
    
    status = inspection_status.lower() if inspection_status else 'in_progress'
    role_level = get_role_level(user_role)
    
    # Terminal states = locked for everyone
    if status in ('closed', 'certified', 'pending_followup'):
        return False, 'This inspection is closed and cannot be edited.'
    
    # Manager/admin can edit anything except terminal states
    if role_level >= get_role_level('manager'):
        return True, None
    
    # Team lead can edit in_progress and submitted
    if role_level >= get_role_level('team_lead'):
        if status in ('in_progress', 'submitted'):
            return True, None
        else:
            return False, f'This inspection is {status}. Only managers can edit.'
    
    # Inspector can only edit in_progress
    if status == 'in_progress':
        return True, None
    else:
        return False, f'This inspection has been submitted and is locked for editing.'


def get_status_info_for_role(inspection_status, user_role):
    """
    Get status display info for the inspection banner.
    Returns dict with: locked, message, next_action, can_take_action
    """
    if inspection_status is None:
        inspection_status = 'in_progress'
    
    status = inspection_status.lower()
    role_level = get_role_level(user_role)
    can_edit, lock_reason = can_edit_inspection(status, user_role)
    
    status_map = {
        'in_progress': {
            'locked': False,
            'message': 'Inspection in progress',
            'next_action': 'Submit when 100% complete',
            'badge_color': 'blue'
        },
        'submitted': {
            'locked': role_level < get_role_level('team_lead'),
            'message': 'Submitted - Awaiting Team Lead review',
            'next_action': 'Mark as Reviewed' if role_level >= get_role_level('team_lead') else None,
            'badge_color': 'purple'
        },
        'reviewed': {
            'locked': role_level < get_role_level('manager'),
            'message': 'Reviewed - Awaiting Manager approval',
            'next_action': 'Approve' if role_level >= get_role_level('manager') else None,
            'badge_color': 'indigo'
        },
        'approved': {
            'locked': role_level < get_role_level('manager'),
            'message': 'Approved - Ready for PDF and close',
            'next_action': 'Generate PDF' if role_level >= get_role_level('manager') else None,
            'badge_color': 'green'
        },
        'certified': {
            'locked': True,
            'message': 'Certified - Unit signed off, no defects',
            'next_action': None,
            'badge_color': 'green'
        },
        'pending_followup': {
            'locked': True,
            'message': 'Closed - Defects remain, next cycle required',
            'next_action': None,
            'badge_color': 'orange'
        },
        'closed': {
            'locked': True,
            'message': 'Closed - No further edits allowed',
            'next_action': None,
            'badge_color': 'gray'
        }
    }
    
    info = status_map.get(status, status_map['in_progress'])
    info['can_edit'] = can_edit
    info['lock_reason'] = lock_reason
    info['status'] = status
    
    return info


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
