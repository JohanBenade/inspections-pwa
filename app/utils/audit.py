"""
Audit Log Helper
Provides log_audit() function for recording all state changes.

Usage:
    from app.utils.audit import log_audit

    log_audit(
        db=conn,
        tenant_id='MONOGRAPH',
        entity_type='inspection',
        entity_id=inspection_id,
        action='status_change',
        old_value='submitted',
        new_value='under_review',
        user_id=current_user.id,
        user_name=current_user.name
    )
"""

import uuid
from datetime import datetime, timezone


def log_audit(db, tenant_id, entity_type, entity_id, action,
              old_value=None, new_value=None,
              user_id=None, user_name=None, metadata=None):
    """
    Record an audit trail entry.

    Args:
        db: SQLite connection
        tenant_id: Tenant identifier (e.g., 'MONOGRAPH')
        entity_type: 'inspection', 'unit', 'cycle', 'assignment'
        entity_id: ID of the entity being changed
        action: What happened (see ACTION_TYPES below)
        old_value: Previous state (optional)
        new_value: New state (optional)
        user_id: Who performed the action
        user_name: Display name (denormalized for quick reads)
        metadata: JSON string with extra context (optional)
    """
    audit_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    db.execute(
        '''INSERT INTO audit_log
           (id, tenant_id, entity_type, entity_id, action,
            old_value, new_value, user_id, user_name, metadata, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (audit_id, tenant_id, entity_type, entity_id, action,
         old_value, new_value,
         user_id or 'system', user_name or 'System',
         metadata, now)
    )

    return audit_id


# --- Standard action types for reference ---
# cycle_created        - New cycle record created
# cycle_started        - Cycle started_at set (first assignment or manual)
# inspector_assigned   - Inspector linked to unit in cycle
# inspection_started   - First item marked by inspector
# item_marked          - Individual item status saved (optional, high volume)
# inspection_submitted - Inspector clicks Submit
# review_started       - Team lead clicks Start Review
# review_submitted     - Team lead clicks Send to Manager
# inspection_approved  - Manager clicks Approve & Close
# unit_certified       - 0 defects at approval, unit complete
# unit_pending_followup - >0 defects at approval, needs next cycle
# status_change        - Generic status change fallback
