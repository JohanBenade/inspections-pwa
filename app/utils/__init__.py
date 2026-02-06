"""
Shared utilities for Inspections PWA.
"""
import uuid


def generate_id(prefix=None):
    """Generate short UUID for database records.
    
    Args:
        prefix: Optional prefix for the ID (e.g., 'cc', 'cch', 'def')
    
    Returns:
        String ID like 'cc-a1b2c3d4' or just 'a1b2c3d4' if no prefix
    """
    short_uuid = str(uuid.uuid4())[:8]
    if prefix:
        return f"{prefix}-{short_uuid}"
    return short_uuid
