"""
Template loader for inspection items.
Loads hierarchical checklist structure for a given unit type.
"""
from app.services.db import get_db


def get_inspection_template(tenant_id: str, unit_type: str) -> list:
    """
    Load complete inspection template for a unit type.
    Returns hierarchical structure: Areas > Categories > Items
    Items marked as is_parent (auto-calculated) or is_markable (user marks).
    """
    db = get_db()
    
    # Get all areas for this unit type
    areas = db.execute("""
        SELECT id, area_name, area_order
        FROM area_template
        WHERE tenant_id = ? AND unit_type = ?
        ORDER BY area_order
    """, [tenant_id, unit_type]).fetchall()
    
    result = []
    for area in areas:
        area_data = {
            'id': area['id'],
            'name': area['area_name'],
            'order': area['area_order'],
            'categories': []
        }
        
        # Get categories for this area
        categories = db.execute("""
            SELECT id, category_name, category_order
            FROM category_template
            WHERE tenant_id = ? AND area_id = ?
            ORDER BY category_order
        """, [tenant_id, area['id']]).fetchall()
        
        for cat in categories:
            cat_data = {
                'id': cat['id'],
                'name': cat['category_name'],
                'order': cat['category_order'],
                'checklist': []
            }
            
            # Get items for this category
            items = db.execute("""
                SELECT id, item_description, item_order, depth, parent_item_id
                FROM item_template
                WHERE tenant_id = ? AND category_id = ?
                ORDER BY item_order
            """, [tenant_id, cat['id']]).fetchall()
            
            # First pass: identify which items have children
            parent_ids = set()
            for item in items:
                if item['parent_item_id']:
                    parent_ids.add(item['parent_item_id'])
            
            # Second pass: build hierarchical structure
            item_map = {}
            for item in items:
                is_parent = item['id'] in parent_ids
                item_data = {
                    'id': item['id'],
                    'description': item['item_description'],
                    'order': item['item_order'],
                    'depth': item['depth'],
                    'parent_id': item['parent_item_id'],
                    'is_parent': is_parent,
                    'is_markable': not is_parent,
                    'children': []
                }
                item_map[item['id']] = item_data
                
                if item['parent_item_id'] is None:
                    cat_data['checklist'].append(item_data)
                elif item['parent_item_id'] in item_map:
                    item_map[item['parent_item_id']]['children'].append(item_data)
            
            area_data['categories'].append(cat_data)
        
        result.append(area_data)
    
    return result


def get_template_item_count(tenant_id: str, unit_type: str) -> int:
    """Get total number of inspection items for a unit type."""
    db = get_db()
    result = db.execute("""
        SELECT COUNT(*) as count
        FROM item_template it
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE at.tenant_id = ? AND at.unit_type = ?
    """, [tenant_id, unit_type]).fetchone()
    return result['count'] if result else 0


def get_area_categories(tenant_id: str, area_id: str) -> list:
    """Get categories for a specific area."""
    db = get_db()
    return db.execute("""
        SELECT id, category_name, category_order
        FROM category_template
        WHERE tenant_id = ? AND area_id = ?
        ORDER BY category_order
    """, [tenant_id, area_id]).fetchall()


def get_category_items(tenant_id: str, category_id: str) -> list:
    """Get items for a specific category with hierarchy and parent/markable flags."""
    db = get_db()
    items = db.execute("""
        SELECT id, item_description, item_order, depth, parent_item_id
        FROM item_template
        WHERE tenant_id = ? AND category_id = ?
        ORDER BY item_order
    """, [tenant_id, category_id]).fetchall()
    
    # First pass: identify which items have children
    parent_ids = set()
    for item in items:
        if item['parent_item_id']:
            parent_ids.add(item['parent_item_id'])
    
    # Build hierarchical structure
    result = []
    item_map = {}
    
    for item in items:
        is_parent = item['id'] in parent_ids
        item_data = {
            'id': item['id'],
            'description': item['item_description'],
            'order': item['item_order'],
            'depth': item['depth'],
            'parent_id': item['parent_item_id'],
            'is_parent': is_parent,
            'is_markable': not is_parent,
            'children': []
        }
        item_map[item['id']] = item_data
        
        if item['parent_item_id'] is None:
            result.append(item_data)
        elif item['parent_item_id'] in item_map:
            item_map[item['parent_item_id']]['children'].append(item_data)
    
    return result


def flatten_items(items: list) -> list:
    """Flatten hierarchical items into a single list with depth info."""
    result = []
    for item in items:
        result.append(item)
        if item.get('children'):
            for child in item['children']:
                result.append(child)
    return result


def calculate_parent_status(children_statuses: list) -> str:
    """
    Calculate parent status from children.
    - All OK -> OK
    - All N/A -> N/A
    - Any NTS/NI -> defective (show as NTS)
    - Mix of OK and N/A -> OK
    - Any pending -> pending
    """
    if not children_statuses:
        return 'pending'
    
    statuses = set(children_statuses)
    
    # Any pending = parent pending
    if 'pending' in statuses:
        return 'pending'
    
    # Any defect = parent shows defective
    if 'not_to_standard' in statuses or 'not_installed' in statuses:
        return 'not_to_standard'
    
    # All N/A = parent N/A
    if statuses == {'not_applicable'}:
        return 'not_applicable'
    
    # Otherwise OK (includes mix of OK and N/A)
    return 'ok'
