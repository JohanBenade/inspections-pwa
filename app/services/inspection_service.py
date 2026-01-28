"""
Inspection service - Shared logic for inspection workflows.
"""
from app.services.db import query_db
from app.services.template_loader import get_category_items, flatten_items


def get_area_with_statuses(tenant_id: str, inspection_id: str, area_id: str) -> dict:
    """
    Load area data with current item statuses for an inspection.
    Returns dict with area info and categories containing flat item lists.
    """
    area = query_db(
        "SELECT * FROM area_template WHERE id = ?",
        [area_id], one=True
    )
    
    if not area:
        return None
    
    categories = query_db("""
        SELECT * FROM category_template 
        WHERE area_id = ? 
        ORDER BY category_order
    """, [area_id])
    
    categories_data = []
    for cat in categories:
        items = get_category_items(tenant_id, cat['id'])
        flat_items = flatten_items(items)
        
        # Build map for parent lookup
        item_map = {item['id']: item for item in flat_items}
        
        # Get status for all items from database
        for item in flat_items:
            status = query_db("""
                SELECT status, comment FROM inspection_item
                WHERE inspection_id = ? AND item_template_id = ?
            """, [inspection_id, item['id']], one=True)
            item['status'] = status['status'] if status else 'pending'
            item['comment'] = status['comment'] if status else None
        
        # Add parent_status to children
        for item in flat_items:
            if item.get('parent_id') and item['parent_id'] in item_map:
                item['parent_status'] = item_map[item['parent_id']]['status']
            else:
                item['parent_status'] = None
        
        categories_data.append({
            'id': cat['id'],
            'name': cat['category_name'],
            'checklist': flat_items
        })
    
    return {
        'area': area,
        'categories': categories_data
    }
