"""
Approvals routes - Kevin's command centre.
Review defect descriptions, mark units reviewed, sign off cycles, push PDFs.
Roles: manager + admin only.
"""
import os
import io
import zipfile
import base64
import json
import urllib.request
import urllib.error
import requests
from datetime import datetime, timezone
from difflib import SequenceMatcher
from collections import OrderedDict
from flask import (Blueprint, render_template, session, redirect,
                   url_for, abort, request, flash, send_file)
from app.auth import require_manager, require_team_lead
from app.utils import generate_id
from app.utils.audit import log_audit
from app.services.db import get_db, query_db

approvals_bp = Blueprint('approvals', __name__, url_prefix='/approvals')


# ============================================================
# HELPERS
# ============================================================

def _get_cycle_pipeline(tenant_id):
    """Build pipeline data for all non-test cycles."""
    cycles = [dict(r) for r in query_db("""
        SELECT ic.*,
            (SELECT COUNT(DISTINCT i.id)
             FROM inspection i WHERE i.cycle_id = ic.id) AS total_inspections,
            (SELECT COUNT(DISTINCT i.id)
             FROM inspection i WHERE i.cycle_id = ic.id AND i.status = 'submitted') AS submitted_count,
            (SELECT COUNT(DISTINCT i.id)
             FROM inspection i WHERE i.cycle_id = ic.id AND i.status IN ('reviewed','pending_followup')) AS reviewed_count,
            (SELECT COUNT(DISTINCT i.id)
             FROM inspection i WHERE i.cycle_id = ic.id
             AND i.status IN ('pending_followup', 'certified', 'closed')) AS signed_off_count,
            (SELECT COUNT(*) FROM defect d
             WHERE d.raised_cycle_id = ic.id AND d.status = 'open'
             AND d.tenant_id = ic.tenant_id) AS defect_count,
            (SELECT MIN(i.submitted_at) FROM inspection i
             WHERE i.cycle_id = ic.id AND i.submitted_at IS NOT NULL) AS first_submitted_at,
            (SELECT MAX(i.updated_at) FROM inspection i
             WHERE i.cycle_id = ic.id AND i.status IN ('reviewed', 'pending_followup', 'certified', 'closed')) AS last_reviewed_at
        FROM inspection_cycle ic
        WHERE ic.tenant_id = ? AND ic.id NOT LIKE 'test-%'
        ORDER BY ic.created_at DESC
    """, [tenant_id])]

    for c in cycles:
        total = c['total_inspections']
        c['has_inspections'] = total > 0
        # Pipeline stage
        if c['pdfs_pushed_at']:
            c['stage'] = 'pushed'
            c['stage_label'] = 'PDFs Pushed'
        elif c['approved_at']:
            c['stage'] = 'signed_off'
            c['stage_label'] = 'Signed Off'
        elif c['reviewed_count'] == total and total > 0:
            c['stage'] = 'all_reviewed'
            c['stage_label'] = 'All Reviewed'
        elif c['reviewed_count'] > 0:
            c['stage'] = 'reviewing'
            c['stage_label'] = 'Reviewing'
        elif c['submitted_count'] > 0:
            c['stage'] = 'submitted'
            c['stage_label'] = 'Submitted'
        else:
            c['stage'] = 'in_progress'
            c['stage_label'] = 'In Progress'

        # Count descriptions needing attention
        if total > 0:
            c['needs_attention'] = _count_needs_attention(tenant_id, c['id'])
        else:
            c['needs_attention'] = 0

    return cycles


def _count_needs_attention(tenant_id, cycle_id):
    """Count defects whose description is not in the library for its category."""
    defects = query_db("""
        SELECT d.id,
               COALESCE(d.reviewed_comment, d.original_comment) AS display_desc,
               d.item_template_id
        FROM defect d
        JOIN inspection i ON i.unit_id = d.unit_id AND i.cycle_id = d.raised_cycle_id
            AND i.tenant_id = d.tenant_id
        WHERE d.raised_cycle_id = ? AND d.status = 'open' AND d.tenant_id = ?
        AND i.status NOT IN ('reviewed','pending_followup','approved','certified','closed')
    """, [cycle_id, tenant_id])

    if not defects:
        return 0

    # All library entries grouped by category (regardless of item_template_id)
    lib_all = query_db("""
        SELECT dl.category_name, LOWER(dl.description) AS desc_lower
        FROM defect_library dl
        WHERE dl.tenant_id = ?
    """, [tenant_id])

    lib_by_cat = {}
    for entry in lib_all:
        cat = entry['category_name']
        if cat not in lib_by_cat:
            lib_by_cat[cat] = set()
        lib_by_cat[cat].add(entry['desc_lower'])

    # Map template_id -> category_name
    template_ids = set(d['item_template_id'] for d in defects if d['item_template_id'])
    cat_by_template = {}
    if template_ids:
        placeholders = ','.join('?' for _ in template_ids)
        cats = query_db("""
            SELECT it.id AS tid, ct.category_name
            FROM item_template it
            JOIN category_template ct ON it.category_id = ct.id
            WHERE it.id IN ({})
        """.format(placeholders), list(template_ids))
        for c in cats:
            cat_by_template[c['tid']] = c['category_name']

    count = 0
    for d in defects:
        desc_lower = (d['display_desc'] or '').lower().strip()
        tid = d['item_template_id']
        cat_name = cat_by_template.get(tid)
        if cat_name and cat_name in lib_by_cat and desc_lower in lib_by_cat[cat_name]:
            continue
        count += 1

    return count




def _get_batch_pipeline(tenant_id):
    """Build pipeline data grouped by batch, with zones (cycles) nested inside."""
    batches_raw = query_db("""
        SELECT ib.*
        FROM inspection_batch ib
        WHERE ib.tenant_id = ?
        ORDER BY ib.created_at DESC
    """, [tenant_id])

    result = []
    for b in batches_raw:
        batch = dict(b)

        # Days elapsed - set after milestones query
        batch['days_elapsed'] = 0

        # Get zones (distinct cycles) in this batch
        zones_raw = query_db("""
            SELECT ic.id as cycle_id, ic.block, ic.floor, ic.cycle_number,
                   ic.approved_at, ic.pdfs_pushed_at,
                   COUNT(DISTINCT bu.unit_id) as batch_unit_count
            FROM batch_unit bu
            JOIN inspection_cycle ic ON bu.cycle_id = ic.id
            WHERE bu.batch_id = ? AND bu.tenant_id = ?
            GROUP BY ic.id
            ORDER BY ic.block, ic.floor, ic.cycle_number
        """, [batch['id'], tenant_id])

        zones = []
        total_units = 0
        for z in zones_raw:
            zone = dict(z)
            total_units += zone['batch_unit_count']

            # Full cycle stats (all units in cycle)
            cs = query_db("""
                SELECT
                    COUNT(DISTINCT i.id) as total_inspections,
                    COUNT(DISTINCT CASE WHEN i.status = 'submitted' THEN i.id END) as submitted_count,
                    COUNT(DISTINCT CASE WHEN i.status IN ('reviewed','pending_followup') THEN i.id END) as reviewed_count,
                    COUNT(DISTINCT CASE WHEN i.status IN ('pending_followup', 'certified', 'closed') THEN i.id END) as signed_count,
                    (SELECT COUNT(*) FROM defect d WHERE d.raised_cycle_id = ?
                     AND d.status = 'open' AND d.tenant_id = ?) as defect_count
                FROM inspection i
                WHERE i.cycle_id = ? AND i.tenant_id = ?
            """, [zone['cycle_id'], tenant_id, zone['cycle_id'], tenant_id], one=True)

            if cs:
                zone.update(dict(cs))
            else:
                zone['total_inspections'] = 0
                zone['submitted_count'] = 0
                zone['reviewed_count'] = 0
                zone['signed_count'] = 0
                zone['defect_count'] = 0

            total = zone['total_inspections']
            zone['needs_attention'] = _count_needs_attention(tenant_id, zone['cycle_id']) if total > 0 else 0

            if zone.get('pdfs_pushed_at'):
                zone['stage'] = 'pushed'
                zone['stage_label'] = 'PDFs Pushed'
            elif zone.get('approved_at'):
                zone['stage'] = 'signed_off'
                zone['stage_label'] = 'Signed Off'
            elif zone['reviewed_count'] == zone['batch_unit_count'] and zone['batch_unit_count'] > 0:
                zone['stage'] = 'all_reviewed'
                zone['stage_label'] = 'All Reviewed'
            elif zone['reviewed_count'] > 0:
                zone['stage'] = 'reviewing'
                zone['stage_label'] = 'Reviewing'
            elif zone['submitted_count'] > 0:
                zone['stage'] = 'submitted'
                zone['stage_label'] = 'Submitted'
            else:
                zone['stage'] = 'in_progress'
                zone['stage_label'] = 'In Progress'

            # Floor label
            floor_map = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor', 3: '3rd Floor'}
            zone['floor_label'] = floor_map.get(zone['floor'], 'Floor ' + str(zone['floor']))

            # First submitted date
            sub_date = query_db(
                "SELECT MIN(submitted_at) as d FROM inspection WHERE cycle_id = ? AND submitted_at IS NOT NULL",
                [zone['cycle_id']], one=True)
            zone['first_submitted_date'] = sub_date['d'][:10] if sub_date and sub_date['d'] else None

            zones.append(zone)

        batch['zones'] = zones
        batch['total_units'] = total_units

        # Batch overall stage = worst zone
        if zones:
            stage_order = ['in_progress', 'submitted', 'reviewing', 'all_reviewed', 'signed_off', 'pushed']
            zone_stages = [z['stage'] for z in zones]
            worst = min(zone_stages, key=lambda s: stage_order.index(s) if s in stage_order else 0)
            batch['stage'] = worst
            batch['stage_label'] = next(z['stage_label'] for z in zones if z['stage'] == worst)
        else:
            batch['stage'] = 'open'
            batch['stage_label'] = 'Open'



        # Milestone dates from inspections in this batch
        milestones = query_db("""
            SELECT
                MIN(i.inspection_date) as earliest_inspection,
                MAX(i.submitted_at) as last_submitted,
                MAX(CASE WHEN i.status IN ('reviewed','pending_followup','certified','closed')
                    THEN i.updated_at END) as last_reviewed
            FROM batch_unit bu
            JOIN inspection i ON i.unit_id = bu.unit_id AND i.cycle_id = bu.cycle_id
            WHERE bu.batch_id = ? AND bu.tenant_id = ?
        """, [batch['id'], tenant_id], one=True)

        if milestones:
            batch['last_submitted_date'] = milestones['last_submitted'][:10] if milestones['last_submitted'] else None
            batch['last_reviewed_date'] = milestones['last_reviewed'][:10] if milestones['last_reviewed'] else None
            # Received = Monday before earliest inspection date
            ei = milestones['earliest_inspection']
            if ei:
                from datetime import timedelta
                ei_date = datetime.strptime(ei, '%Y-%m-%d')
                monday = ei_date - timedelta(days=ei_date.weekday())
                batch['created_date'] = monday.strftime('%Y-%m-%d')
                elapsed = (datetime.now(timezone.utc) - datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)).days
                batch['days_elapsed'] = elapsed
            else:
                batch['created_date'] = batch['created_at'][:10]
        else:
            batch['created_date'] = batch['created_at'][:10]
            batch['last_submitted_date'] = None
            batch['last_reviewed_date'] = None

        # Signed off / pushed dates from cycles
        cycle_dates = query_db("""
            SELECT MAX(ic.approved_at) as last_approved, MAX(ic.pdfs_pushed_at) as last_pushed
            FROM batch_unit bu
            JOIN inspection_cycle ic ON bu.cycle_id = ic.id
            WHERE bu.batch_id = ? AND bu.tenant_id = ?
        """, [batch['id'], tenant_id], one=True)

        if cycle_dates:
            batch['signed_off_date'] = cycle_dates['last_approved'][:10] if cycle_dates['last_approved'] else None
            batch['pushed_date'] = cycle_dates['last_pushed'][:10] if cycle_dates['last_pushed'] else None
        else:
            batch['signed_off_date'] = None
            batch['pushed_date'] = None

        # Categorise batch for sections (only count zones with actual inspections)
        active_zones = [z for z in zones if z['total_inspections'] > 0]

        if not active_zones:
            batch['section'] = 'progress'
            batch['stage'] = 'open'
            batch['stage_label'] = 'Open'
        else:
            all_pushed = all(z['stage'] == 'pushed' for z in active_zones)
            all_signed = all(z['stage'] in ('signed_off', 'pushed') for z in active_zones)
            all_reviewed = all(z['stage'] in ('all_reviewed', 'signed_off', 'pushed') for z in active_zones)
            any_progress = any(z['stage'] in ('in_progress', 'submitted', 'reviewing') for z in active_zones)

            if all_pushed:
                batch['section'] = 'complete'
                batch['stage'] = 'pushed'
                batch['stage_label'] = 'PDFs Pushed'
            elif all_signed:
                batch['section'] = 'complete'
                batch['stage'] = 'signed_off'
                batch['stage_label'] = 'Signed Off'
            elif all_reviewed:
                batch['section'] = 'ready'
                batch['stage'] = 'all_reviewed'
                batch['stage_label'] = 'All Reviewed'
            elif any_progress:
                batch['section'] = 'progress'
                batch['stage'] = 'in_progress'
                batch['stage_label'] = 'In Progress'
            else:
                batch['section'] = 'progress'
                batch['stage'] = 'submitted'
                batch['stage_label'] = 'Submitted'

        result.append(batch)

    return result

def _build_review_data(tenant_id, cycle_id):
    """Build complete review data for a cycle."""
    cycle = query_db(
        "SELECT * FROM inspection_cycle WHERE id = ? AND tenant_id = ?",
        [cycle_id, tenant_id], one=True)
    if not cycle:
        return None
    cycle = dict(cycle)

    # All inspections in this cycle
    inspections = [dict(r) for r in query_db("""
        SELECT i.id, i.unit_id, i.status, i.inspector_name,
               u.unit_number, u.block, u.floor
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        WHERE i.cycle_id = ? AND i.tenant_id = ?
        ORDER BY u.unit_number
    """, [cycle_id, tenant_id])]

    # Compute unit range for display
    unit_numbers = sorted([insp['unit_number'] for insp in inspections])
    cycle['unit_start'] = unit_numbers[0] if unit_numbers else ''
    cycle['unit_end'] = unit_numbers[-1] if unit_numbers else ''

    # Compute unit range for display
    unit_numbers = sorted([insp['unit_number'] for insp in inspections])
    cycle['unit_start'] = unit_numbers[0] if unit_numbers else ''
    cycle['unit_end'] = unit_numbers[-1] if unit_numbers else ''

    if not inspections:
        return {'cycle': cycle, 'units': [], 'stats': {
            'total': 0, 'reviewed': 0, 'defects': 0, 'to_fix': 0}}

    # All open defects for this cycle with template chain
    defects = [dict(r) for r in query_db("""
        SELECT d.id, d.unit_id, d.item_template_id,
               d.original_comment, d.reviewed_comment,
               COALESCE(d.reviewed_comment, d.original_comment) AS display_desc,
               d.defect_type, d.created_at,
               it.item_description,
               parent.item_description AS parent_description,
               ct.category_name, ct.id AS category_id,
               at.area_name, at.area_order, ct.category_order, it.item_order,
               i.status AS insp_status
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        LEFT JOIN item_template parent ON it.parent_item_id = parent.id
        JOIN inspection i ON i.unit_id = d.unit_id AND i.cycle_id = d.raised_cycle_id
        WHERE d.raised_cycle_id = ? AND d.status = 'open' AND d.tenant_id = ?
        ORDER BY at.area_order, ct.category_order, it.item_order
    """, [cycle_id, tenant_id])]

    # Build library lookup: ALL entries grouped by category
    lib_all = query_db("""
        SELECT category_name, LOWER(description) AS desc_lower
        FROM defect_library WHERE tenant_id = ?
    """, [tenant_id])

    lib_by_cat = {}
    for entry in lib_all:
        cat = entry['category_name']
        if cat not in lib_by_cat:
            lib_by_cat[cat] = set()
        lib_by_cat[cat].add(entry['desc_lower'])

    # Mark each defect as clean or needs attention
    reviewed_statuses = {'reviewed', 'pending_followup', 'approved', 'certified', 'closed'}
    for d in defects:
        if d.get('insp_status') in reviewed_statuses:
            d['is_clean'] = True
        else:
            desc_lower = (d['display_desc'] or '').lower().strip()
            cat_name = d['category_name']
            d['is_clean'] = (cat_name in lib_by_cat
                             and desc_lower in lib_by_cat[cat_name])
        # Build full item path
        if d['parent_description']:
            d['item_path'] = '{} > {}'.format(
                d['parent_description'], d['item_description'])
        else:
            d['item_path'] = d['item_description']

    # Group defects by unit
    defects_by_unit = {}
    for d in defects:
        uid = d['unit_id']
        if uid not in defects_by_unit:
            defects_by_unit[uid] = []
        defects_by_unit[uid].append(d)

    # Build unit list with stats
    units = []
    total_to_fix = 0
    total_reviewed = 0
    for insp in inspections:
        uid = insp['unit_id']
        unit_defects = defects_by_unit.get(uid, [])
        to_fix = sum(1 for d in unit_defects if not d['is_clean'])
        total_to_fix += to_fix

        is_reviewed = insp['status'] in ('reviewed', 'pending_followup',
                                         'approved', 'certified', 'closed')
        if is_reviewed:
            total_reviewed += 1

        # Group defects by area then category for display
        grouped = OrderedDict()
        for d in unit_defects:
            area = d['area_name']
            cat = d['category_name']
            if area not in grouped:
                grouped[area] = OrderedDict()
            if cat not in grouped[area]:
                grouped[area][cat] = []
            grouped[area][cat].append(d)

        units.append({
            'unit_id': uid,
            'unit_number': insp['unit_number'],
            'block': insp['block'],
            'floor': insp['floor'],
            'inspection_id': insp['id'],
            'inspection_status': insp['status'],
            'inspector_name': insp['inspector_name'],
            'defect_count': len(unit_defects),
            'to_fix': to_fix,
            'is_reviewed': is_reviewed,
            'can_review': insp['status'] in ('submitted', 'reviewed'),
            'defects_grouped': grouped,
        })

    # Pipeline dates (one query each, not per-unit)
    first_sub = query_db(
        "SELECT MIN(submitted_at) AS val FROM inspection WHERE cycle_id = ? AND submitted_at IS NOT NULL",
        [cycle_id], one=True)
    last_rev = query_db(
        "SELECT MAX(updated_at) AS val FROM inspection WHERE cycle_id = ? AND status IN ('reviewed', 'pending_followup', 'certified', 'closed')",
        [cycle_id], one=True)

    stats = {
        'total': len(inspections),
        'reviewed': total_reviewed,
        'defects': len(defects),
        'to_fix': total_to_fix,
        'first_submitted_at': first_sub['val'] if first_sub else None,
        'last_reviewed_at': last_rev['val'] if last_rev else None,
    }

    return {'cycle': cycle, 'units': units, 'stats': stats}


def _get_suggestions(tenant_id, item_template_id, exclude_desc=None):
    """Get suggestion pills for a defect (two-tier: item then category)."""
    suggestions = [dict(r) for r in query_db("""
        SELECT id, description, usage_count FROM defect_library
        WHERE tenant_id = ? AND item_template_id = ?
        ORDER BY usage_count DESC LIMIT 6
    """, [tenant_id, item_template_id])]

    if not suggestions:
        cat = query_db("""
            SELECT ct.category_name
            FROM item_template it
            JOIN category_template ct ON it.category_id = ct.id
            WHERE it.id = ?
        """, [item_template_id], one=True)
        if cat:
            suggestions = [dict(r) for r in query_db("""
                SELECT id, description, usage_count FROM defect_library
                WHERE tenant_id = ? AND category_name = ?
                AND item_template_id IS NULL
                ORDER BY usage_count DESC LIMIT 5
            """, [tenant_id, cat['category_name']])]

    # Exclude current description
    if exclude_desc:
        exclude_lower = exclude_desc.lower().strip()
        suggestions = [s for s in suggestions
                       if s['description'].lower().strip() != exclude_lower]

    return suggestions[:5]


# ============================================================
# ROUTES
# ============================================================

@approvals_bp.route('/')
@require_manager
def pipeline():
    """Pipeline overview - all cycles with status."""
    tenant_id = session['tenant_id']
    batches = _get_batch_pipeline(tenant_id)
    return render_template('approvals/pipeline.html', batches=batches)


@approvals_bp.route('/batch/<batch_id>/set-milestone', methods=['POST'])
@require_manager
def set_batch_milestone(batch_id):
    """Move all units in a batch to a target milestone status."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    milestone = request.form.get('milestone')
    STATUS_MAP = {
        'received':   'not_started',
        'inspected':  'submitted',
        'reviewed':   'reviewed',
        'signed_off': 'pending_followup',
        'pushed':     'pending_followup',
    }
    if milestone not in STATUS_MAP:
        abort(400)

    target_status = STATUS_MAP[milestone]

    # Get all units in batch
    units = query_db("""
        SELECT bu.id as bu_id, i.id as insp_id
        FROM batch_unit bu
        LEFT JOIN inspection i ON i.unit_id = bu.unit_id AND i.cycle_id = bu.cycle_id
        WHERE bu.batch_id = ? AND bu.tenant_id = ? AND bu.status != 'removed'
    """, [batch_id, tenant_id])

    for u in units:
        if u['insp_id']:
            db.execute("""
                UPDATE inspection SET status = ?, updated_at = ? WHERE id = ?
            """, [target_status, now, u['insp_id']])
        db.execute("""
            UPDATE batch_unit SET status = ? WHERE id = ?
        """, [target_status, u['bu_id']])

    log_audit(db, tenant_id, 'batch', batch_id, 'milestone_set',
              new_value=milestone,
              user_id=session['user_id'], user_name=session['user_name'])

    db.commit()

    from flask import jsonify
    return jsonify({'ok': True})


@approvals_bp.route('/<cycle_id>/')
@require_manager
def review(cycle_id):
    """Main review screen for a cycle."""
    tenant_id = session['tenant_id']
    data = _build_review_data(tenant_id, cycle_id)
    if not data:
        abort(404)

    # Pre-load suggestions for defects that need attention (not clean)
    for unit in data['units']:
        for area_cats in unit['defects_grouped'].values():
            for defect_list in area_cats.values():
                for d in defect_list:
                    if not d['is_clean']:
                        d['suggestions'] = _get_suggestions(
                            tenant_id, d['item_template_id'],
                            d['display_desc'])
                    else:
                        d['suggestions'] = []

    return render_template('approvals/review.html', **data)


@approvals_bp.route('/<cycle_id>/edit-defect', methods=['POST'])
@require_manager
def edit_defect(cycle_id):
    """Update a defect's reviewed_comment (pill tap or manual edit)."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    defect_id = request.form.get('defect_id')
    new_desc = request.form.get('description', '').strip()
    library_entry_id = request.form.get('library_entry_id')  # Set if pill tap

    if not defect_id or not new_desc:
        abort(400)

    # Verify defect exists and belongs to this cycle
    defect = query_db("""
        SELECT d.*, it.item_description,
               ct.category_name, d.item_template_id
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        WHERE d.id = ? AND d.raised_cycle_id = ? AND d.tenant_id = ?
    """, [defect_id, cycle_id, tenant_id], one=True)

    if not defect:
        abort(404)

    old_desc = defect['reviewed_comment'] or defect['original_comment']

    # 1. Update defect reviewed_comment
    db.execute("""
        UPDATE defect SET reviewed_comment = ?, updated_at = ?
        WHERE id = ?
    """, [new_desc, now, defect_id])

    # 2. Handle library
    if library_entry_id:
        # Pill tap - increment usage count
        db.execute("""
            UPDATE defect_library SET usage_count = usage_count + 1
            WHERE id = ? AND tenant_id = ?
        """, [library_entry_id, tenant_id])
    else:
        # Manual edit - check if near-duplicate exists (0.95 threshold)
        existing = query_db("""
            SELECT id, description FROM defect_library
            WHERE tenant_id = ? AND item_template_id = ?
        """, [tenant_id, defect['item_template_id']])

        matched = False
        for entry in existing:
            score = SequenceMatcher(
                None, new_desc.lower(), entry['description'].lower()).ratio()
            if score >= 0.95:
                # Near-duplicate - increment existing
                db.execute("""
                    UPDATE defect_library SET usage_count = usage_count + 1
                    WHERE id = ?
                """, [entry['id']])
                matched = True
                break

        if not matched:
            # New library entry
            lib_id = generate_id()
            db.execute("""
                INSERT INTO defect_library
                (id, tenant_id, category_name, item_template_id,
                 description, usage_count, is_system, created_at)
                VALUES (?, ?, ?, ?, ?, 1, 0, ?)
            """, [lib_id, tenant_id, defect['category_name'],
                  defect['item_template_id'], new_desc, now])

    # 3. Audit trail
    log_audit(db, tenant_id, 'defect', defect_id, 'review_edit',
              old_value=old_desc, new_value=new_desc,
              user_id=session['user_id'], user_name=session['user_name'])

    db.commit()

    # Return updated defect row via HTMX
    is_htmx = request.headers.get('HX-Request')
    if is_htmx:
        return _render_defect_row(defect_id, cycle_id, tenant_id, is_clean=True)

    return redirect(url_for('approvals.review', cycle_id=cycle_id))


@approvals_bp.route('/<cycle_id>/mark-reviewed', methods=['POST'])
@require_manager
def mark_reviewed(cycle_id):
    """Mark a single unit's inspection as reviewed."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    inspection_id = request.form.get('inspection_id')
    if not inspection_id:
        abort(400)

    insp = query_db("""
        SELECT i.*, u.unit_number
        FROM inspection i JOIN unit u ON i.unit_id = u.id
        WHERE i.id = ? AND i.cycle_id = ? AND i.tenant_id = ?
    """, [inspection_id, cycle_id, tenant_id], one=True)

    if not insp:
        abort(404)

    if insp['status'] not in ('submitted', 'in_progress'):
        # Already reviewed or beyond
        is_htmx = request.headers.get('HX-Request')
        if is_htmx:
            return '<span class="text-green-600 text-sm font-medium">Already reviewed</span>'
        return redirect(url_for('approvals.review', cycle_id=cycle_id))

    db.execute("""
        UPDATE inspection SET status = 'reviewed', updated_at = ?
        WHERE id = ?
    """, [now, inspection_id])

    log_audit(db, tenant_id, 'inspection', inspection_id, 'reviewed',
              old_value=insp['status'], new_value='reviewed',
              user_id=session['user_id'], user_name=session['user_name'],
              metadata='{{"unit": "{}"}}'.format(insp['unit_number']))

    db.commit()

    is_htmx = request.headers.get('HX-Request')
    if is_htmx:
        return '''<div class="flex items-center gap-2">
            <span class="inline-block w-2 h-2 rounded-full bg-green-500"></span>
            <span class="text-green-600 text-sm font-medium">Reviewed</span>
        </div>'''

    return redirect(url_for('approvals.review', cycle_id=cycle_id))


@approvals_bp.route('/<cycle_id>/bulk-reviewed', methods=['POST'])
@require_manager
def bulk_reviewed(cycle_id):
    """Mark all clean units (zero to-fix) as reviewed."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    data = _build_review_data(tenant_id, cycle_id)
    if not data:
        abort(404)

    marked = 0
    skipped = 0
    for unit in data['units']:
        if unit['is_reviewed']:
            continue
        if unit['inspection_status'] not in ('submitted', 'in_progress'):
            continue
        if unit['to_fix'] > 0:
            skipped += 1
            continue

        db.execute("""
            UPDATE inspection SET status = 'reviewed', updated_at = ?
            WHERE id = ?
        """, [now, unit['inspection_id']])

        log_audit(db, tenant_id, 'inspection', unit['inspection_id'],
                  'reviewed',
                  old_value=unit['inspection_status'], new_value='reviewed',
                  user_id=session['user_id'], user_name=session['user_name'],
                  metadata='{{"unit": "{}", "bulk": true}}'.format(
                      unit['unit_number']))
        marked += 1

    db.commit()

    msg = '{} units marked as reviewed.'.format(marked)
    if skipped > 0:
        msg += ' {} skipped (descriptions need attention).'.format(skipped)
    flash(msg, 'success')

    return redirect(url_for('approvals.review', cycle_id=cycle_id))


@approvals_bp.route('/<cycle_id>/sign-off', methods=['POST'])
@require_manager
def sign_off(cycle_id):
    """Bulk sign off all reviewed units in a cycle."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    cycle = query_db(
        "SELECT * FROM inspection_cycle WHERE id = ? AND tenant_id = ?",
        [cycle_id, tenant_id], one=True)

    if not cycle:
        abort(404)

    if cycle['approved_at']:
        flash('This cycle has already been signed off.', 'error')
        return redirect(url_for('approvals.review', cycle_id=cycle_id))

    # Move all reviewed inspections to pending_followup
    db.execute("""
        UPDATE inspection SET status = 'pending_followup', updated_at = ?
        WHERE cycle_id = ? AND tenant_id = ? AND status = 'reviewed'
    """, [now, cycle_id, tenant_id])
    updated = db.execute("SELECT changes()").fetchone()[0]

    # Set cycle approval
    db.execute("""
        UPDATE inspection_cycle SET approved_at = ?, approved_by = ?
        WHERE id = ?
    """, [now, session['user_name'], cycle_id])

    log_audit(db, tenant_id, 'cycle', cycle_id, 'approved',
              new_value='signed_off',
              user_id=session['user_id'], user_name=session['user_name'])

    db.commit()

    block = cycle['block'] or 'Cycle'
    flash('Signed off {} - {} units approved for Raubex.'.format(
        block, updated), 'success')
    if request.form.get('from_page') == 'pipeline':
        return redirect(url_for('approvals.pipeline'))
    return redirect(url_for('approvals.review', cycle_id=cycle_id))


@approvals_bp.route('/<cycle_id>/push-pdfs', methods=['POST'])
@require_manager
def push_pdfs(cycle_id):
    """Generate all PDFs for cycle and return as ZIP download."""
    from app.services.pdf_generator import generate_defects_pdf, generate_pdf_filename

    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    cycle = query_db(
        "SELECT * FROM inspection_cycle WHERE id = ? AND tenant_id = ?",
        [cycle_id, tenant_id], one=True)

    if not cycle:
        abort(404)

    if not cycle['approved_at']:
        flash('Cycle must be signed off before downloading PDFs.', 'error')
        return redirect(url_for('approvals.review', cycle_id=cycle_id))

    # No block on re-download -- Kevin can download ZIP multiple times

    units = [dict(r) for r in query_db("""
        SELECT u.id, u.unit_number, u.block, u.floor,
               i.inspection_date, i.id AS inspection_id
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        WHERE i.cycle_id = ? AND i.tenant_id = ?
        ORDER BY u.unit_number
    """, [cycle_id, tenant_id])]

    if not units:
        flash('No units found in this cycle.', 'error')
        return redirect(url_for('approvals.review', cycle_id=cycle_id))

    zip_buffer = io.BytesIO()
    success_count = 0
    fail_count = 0

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for unit in units:
            try:
                pdf_bytes = generate_defects_pdf(tenant_id, unit['id'], cycle_id)
                if not pdf_bytes:
                    fail_count += 1
                    continue
                filename = generate_pdf_filename(
                    unit, dict(cycle),
                    inspection_date=unit.get('inspection_date'))
                zf.writestr(filename, pdf_bytes)
                success_count += 1
            except Exception:
                fail_count += 1

    if success_count == 0:
        flash('PDF generation failed for all units.', 'error')
        return redirect(url_for('approvals.review', cycle_id=cycle_id))

    # Mark cycle as downloaded
    db.execute("""
        UPDATE inspection_cycle
        SET pdfs_pushed_at = ?, pdfs_push_status = ?
        WHERE id = ?
    """, [now, 'complete' if fail_count == 0 else 'partial', cycle_id])

    log_audit(db, tenant_id, 'cycle', cycle_id, 'pdfs_downloaded',
              new_value='{}/{} PDFs downloaded'.format(
                  success_count, success_count + fail_count),
              user_id=session['user_id'], user_name=session['user_name'])

    db.commit()

    zip_buffer.seek(0)
    block_label = (cycle['block'] or 'Cycle').replace(' ', '_')
    zip_filename = 'Defect_Reports_{}_{}.zip'.format(
        block_label, cycle_id[:8])

    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_filename
    )


# ============================================================
# HTMX HELPERS
# ============================================================

def _render_defect_row(defect_id, cycle_id, tenant_id, is_clean=True):
    """Render a single defect row after edit (HTMX swap)."""
    d = query_db("""
        SELECT d.id, d.item_template_id,
               d.original_comment, d.reviewed_comment,
               COALESCE(d.reviewed_comment, d.original_comment) AS display_desc,
               d.defect_type,
               it.item_description,
               parent.item_description AS parent_description,
               ct.category_name, at.area_name
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        LEFT JOIN item_template parent ON it.parent_item_id = parent.id
        WHERE d.id = ? AND d.tenant_id = ?
    """, [defect_id, tenant_id], one=True)

    if not d:
        return ''

    if d['parent_description']:
        item_path = '{} > {}'.format(d['parent_description'], d['item_description'])
    else:
        item_path = d['item_description']

    edited_marker = ''
    if d['reviewed_comment'] and d['reviewed_comment'] != d['original_comment']:
        edited_marker = (
            '<div class="text-xs text-gray-400 mt-0.5 line-through">'
            '{}</div>'.format(d['original_comment']))

    return '''
    <div class="defect-row flex items-start gap-3 py-2.5 px-3 bg-white rounded-lg border border-green-200"
         id="defect-{id}">
        <div class="flex-shrink-0 mt-1">
            <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-green-100">
                <svg class="w-3 h-3 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
                </svg>
            </span>
        </div>
        <div class="flex-1 min-w-0">
            <div class="text-xs text-gray-400">{item_path}</div>
            <div class="text-sm text-green-700 font-medium">{desc}</div>
            {edited}
        </div>
    </div>
    '''.format(
        id=d['id'],
        item_path=item_path,
        desc=d['display_desc'],
        edited=edited_marker
    )

# ============================================================
# DEFECTS CLEANUP - Power tool for description quality
# ============================================================

@approvals_bp.route('/batch/<batch_id>/sign-off', methods=['POST'])
@require_manager
def batch_sign_off(batch_id):
    """Sign off all reviewed cycles in a batch."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    cycles = query_db("""
        SELECT DISTINCT bu.cycle_id, ic.approved_at
        FROM batch_unit bu
        JOIN inspection_cycle ic ON bu.cycle_id = ic.id
        WHERE bu.batch_id = ? AND bu.tenant_id = ? AND bu.status != 'removed'
    """, [batch_id, tenant_id])
    signed = 0
    for cycle in cycles:
        if cycle['approved_at']:
            continue
        db.execute("""
            UPDATE inspection SET status = 'pending_followup', updated_at = ?
            WHERE cycle_id = ? AND tenant_id = ? AND status = 'reviewed'
        """, [now, cycle['cycle_id'], tenant_id])
        db.execute("""
            UPDATE inspection_cycle SET approved_at = ?, approved_by = ?
            WHERE id = ?
        """, [now, session['user_name'], cycle['cycle_id']])
        log_audit(db, tenant_id, 'cycle', cycle['cycle_id'], 'approved',
                  new_value='signed_off',
                  user_id=session['user_id'], user_name=session['user_name'])
        signed += 1
    db.commit()
    from flask import jsonify
    return jsonify({'ok': True, 'signed': signed})


@approvals_bp.route('/batch/<batch_id>/push-pdfs', methods=['POST'])
@require_manager
def batch_push_pdfs(batch_id):
    """Generate PDFs for all units in a batch and return as single ZIP."""
    from app.services.pdf_generator import generate_defects_pdf, generate_pdf_filename
    tenant_id = session['tenant_id']
    print('BATCH_PUSH_PDFS called: batch_id={} tenant={}'.format(batch_id, tenant_id))
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    batch = query_db(
        'SELECT * FROM inspection_batch WHERE id = ? AND tenant_id = ?',
        [batch_id, tenant_id], one=True)
    if not batch:
        abort(404)
    units = [dict(r) for r in query_db("""
        SELECT u.id, u.unit_number, u.block, u.floor,
               i.inspection_date, i.id AS inspection_id,
               bu.cycle_id, ic.cycle_number, ic.approved_at
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        JOIN inspection_cycle ic ON bu.cycle_id = ic.id
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = bu.cycle_id
        WHERE bu.batch_id = ? AND bu.tenant_id = ? AND bu.status != 'removed'
        AND i.id IS NOT NULL
        ORDER BY u.block, u.floor, u.unit_number
    """, [batch_id, tenant_id]) or []]
    print('BATCH_PUSH_PDFS units found: {}'.format(len(units)))
    for u in units:
        print('  unit={} cycle={}'.format(u.get('unit_number'), u.get('cycle_id')))
    if not units:
        from flask import jsonify
        return jsonify({'ok': False, 'error': 'No units found'}), 400
    zip_buffer = io.BytesIO()
    success_count = 0
    fail_count = 0
    cycle_ids = set()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for unit in units:
            cycle_ids.add(unit['cycle_id'])
            try:
                pdf_bytes = generate_defects_pdf(tenant_id, unit['id'], unit['cycle_id'])
                if not pdf_bytes:
                    fail_count += 1
                    continue
                cycle_dict = dict(unit)
                filename = generate_pdf_filename(
                    dict(unit), cycle_dict,
                    inspection_date=unit.get('inspection_date'))
                zf.writestr(filename, pdf_bytes)
                success_count += 1
            except Exception as e:
                import traceback
                print('PDF ERROR unit {}: {}'.format(unit.get('unit_number'), traceback.format_exc()))
                fail_count += 1
    if success_count == 0:
        from flask import jsonify
        return jsonify({'ok': False, 'error': 'PDF generation failed'}), 500
    for cycle_id in cycle_ids:
        db.execute("""
            UPDATE inspection_cycle SET pdfs_pushed_at = ?, pdfs_push_status = ?
            WHERE id = ?
        """, [now, 'complete' if fail_count == 0 else 'partial', cycle_id])
        log_audit(db, tenant_id, 'cycle', cycle_id, 'pdfs_downloaded',
                  new_value='{}/{} PDFs'.format(success_count, success_count + fail_count),
                  user_id=session['user_id'], user_name=session['user_name'])
    db.commit()
    zip_buffer.seek(0)
    batch_name = (batch['name'] or batch_id).replace(' ', '_')
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='Defect_Reports_{}.zip'.format(batch_name)
    )


@approvals_bp.route('/cleanup/')
@require_team_lead
def cleanup():
    """Defects cleanup page - all defects on submitted units."""
    tenant_id = session['tenant_id']

    # Filters from query params
    f_unit = request.args.get('unit', '')
    f_area = request.args.get('area', '')
    f_category = request.args.get('category', '')
    f_status = request.args.get('status', '')  # placeholder / new / clean
    f_inspector = request.args.get('inspector', '')
    f_cycle = request.args.get('cycle', '')
    f_item = request.args.get('item', '')
    f_subitem = request.args.get('subitem', '')
    f_type = request.args.get('type', '')
    f_min_defects = request.args.get('min_defects', '')
    f_batch = request.args.get('batch', '')

    # All defects on submitted inspections
    defects = [dict(r) for r in query_db("""
        SELECT d.id, d.unit_id, d.item_template_id,
               d.original_comment, d.reviewed_comment,
               COALESCE(d.reviewed_comment, d.original_comment) AS display_desc,
               d.defect_type, d.raised_cycle_id, d.created_at, i.id AS inspection_id,
               u.unit_number, u.block, u.floor,
               i.inspector_name, i.status AS insp_status,
               it.item_description,
               parent.item_description AS parent_description,
               ct.category_name, ct.id AS category_id,
               at.area_name, at.area_order, ct.category_order, it.item_order,
               ic.cycle_number, ic.block AS cycle_block, ic.floor AS cycle_floor,
               ib.name AS batch_name, ib.id AS batch_id,
               ib.name AS batch_name, ib.id AS batch_id
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        JOIN inspection i ON i.unit_id = d.unit_id
            AND i.cycle_id = d.raised_cycle_id AND i.tenant_id = d.tenant_id
            AND i.id = (SELECT i2.id FROM inspection i2
                        WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id
                        AND i2.tenant_id = d.tenant_id ORDER BY i2.created_at DESC LIMIT 1)
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
        LEFT JOIN item_template parent ON it.parent_item_id = parent.id
        LEFT JOIN batch_unit bu_link ON bu_link.unit_id = d.unit_id
            AND bu_link.cycle_id = d.raised_cycle_id AND bu_link.status != 'removed'
        LEFT JOIN inspection_batch ib ON bu_link.batch_id = ib.id
        WHERE d.status = 'open' AND d.tenant_id = ?
        AND i.status IN ('submitted','reviewed','pending_followup')
        ORDER BY at.area_order, ct.category_order, it.item_order,
                 u.unit_number
    """, [tenant_id])]

    # Build library lookup
    lib_all = query_db("""
        SELECT category_name, LOWER(TRIM(description)) AS desc_lower
        FROM defect_library WHERE tenant_id = ?
    """, [tenant_id])
    lib_by_cat = {}
    for entry in lib_all:
        cat = entry['category_name']
        if cat not in lib_by_cat:
            lib_by_cat[cat] = set()
        lib_by_cat[cat].add(entry['desc_lower'])

    # Classify each defect
    placeholders = {'defect noted', 'n/a', 'na', 'as indicated', '', 'not applicable yet', 'not applicable', 'not tested', 'to be tested', 'to be inspected'}
    for d in defects:
        desc_lower = (d['display_desc'] or '').lower().strip()
        cat_name = d['category_name']

        # Build item path
        if d['parent_description']:
            d['item_path'] = d['parent_description'] + ' > ' + d['item_description']
        else:
            d['item_path'] = d['item_description']

        # Item/subitem for cascading filters
        if d['parent_description']:
            d['item_name'] = d['parent_description']
            d['subitem_name'] = d['item_description']
        else:
            d['item_name'] = d['item_description']
            d['subitem_name'] = ''

        # Classify
        if desc_lower in placeholders:
            d['cleanup_status'] = 'placeholder'
        elif cat_name in lib_by_cat and desc_lower in lib_by_cat[cat_name]:
            d['cleanup_status'] = 'clean'
        else:
            d['cleanup_status'] = 'new'

        # Cycle label
        floor_map = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor'}
        d['cycle_label'] = (d['cycle_block'] + ' '
                            + floor_map.get(d['cycle_floor'], str(d['cycle_floor']))
                            + ' C' + str(d['cycle_number']))

    # Build filter options from actual data
    all_units = sorted(set(d['unit_number'] for d in defects))
    all_areas = sorted(set(d['area_name'] for d in defects),
                       key=lambda a: next((d['area_order'] for d in defects
                                           if d['area_name'] == a), 0))
    all_categories = sorted(set(d['category_name'] for d in defects))
    # Cascading: items filtered by selected area+category
    items_pool = [d for d in defects
                  if (not f_area or d['area_name'] == f_area)
                  and (not f_category or d['category_name'] == f_category)]
    all_items = sorted(set(d['item_name'] for d in items_pool if d['item_name']))
    # Cascading: subitems filtered by selected item
    subitems_pool = [d for d in items_pool if (not f_item or d['item_name'] == f_item)]
    all_subitems = sorted(set(d['subitem_name'] for d in subitems_pool if d['subitem_name']))
    all_inspectors = sorted(set(d['inspector_name'] for d in defects
                                if d['inspector_name']))
    all_cycles = sorted(set(d['cycle_label'] for d in defects))
    all_batches_raw = query_db(
        "SELECT id, name FROM inspection_batch WHERE tenant_id = ? ORDER BY name",
        [tenant_id])
    all_batches = [(b['id'], b['name']) for b in all_batches_raw]

    # Apply filters
    filtered = defects
    if f_unit:
        filtered = [d for d in filtered if d['unit_number'] == f_unit]
    if f_area:
        filtered = [d for d in filtered if d['area_name'] == f_area]
    if f_category:
        filtered = [d for d in filtered if d['category_name'] == f_category]
    if f_item:
        filtered = [d for d in filtered if d['item_name'] == f_item]
    if f_subitem:
        filtered = [d for d in filtered if d['subitem_name'] == f_subitem]
    if f_type:
        filtered = [d for d in filtered if d['defect_type'] == f_type]
    if f_status:
        filtered = [d for d in filtered if d['cleanup_status'] == f_status]
    if f_inspector:
        filtered = [d for d in filtered if d['inspector_name'] == f_inspector]
    if f_cycle:
        filtered = [d for d in filtered if d['cycle_label'] == f_cycle]
    if f_batch:
        filtered = [d for d in filtered if d.get('batch_id') == f_batch]
    if f_batch:
        filtered = [d for d in filtered if d.get('batch_id') == f_batch]
    if f_min_defects and f_min_defects.isdigit():
        min_d = int(f_min_defects)
        from collections import Counter
        item_unit_counts = Counter((d['unit_id'], d['item_template_id']) for d in defects)
        filtered = [d for d in filtered if item_unit_counts[(d['unit_id'], d['item_template_id'])] > min_d]

    # Sort: placeholder first, then new, then clean
    status_order = {'placeholder': 0, 'new': 1, 'clean': 2}
    filtered.sort(key=lambda d: (
        status_order.get(d['cleanup_status'], 9),
        d['area_order'], d['category_order'], d['item_order'],
        d['unit_number']
    ))

    # Stats
    stats = {
        'total': len(defects),
        'filtered': len(filtered),
        'placeholder': sum(1 for d in filtered if d['cleanup_status'] == 'placeholder'),
        'new': sum(1 for d in filtered if d['cleanup_status'] == 'new'),
        'clean': sum(1 for d in filtered if d['cleanup_status'] == 'clean'),
    }

    # Inspector name when unit filtered
    filtered_inspector = ''
    if f_unit and filtered:
        filtered_inspector = filtered[0].get('inspector_name', '')

    return render_template('approvals/cleanup.html',
                           defects=filtered, stats=stats,
                           filtered_inspector=filtered_inspector,
                           filters={'unit': f_unit, 'area': f_area,
                                    'category': f_category, 'item': f_item,
                                    'subitem': f_subitem, 'type': f_type, 'status': f_status,
                                    'inspector': f_inspector, 'cycle': f_cycle,
                                    'min_defects': f_min_defects, 'batch': f_batch},
                           options={'units': all_units, 'areas': all_areas,
                                    'categories': all_categories,
                                    'item_names': all_items,
                                    'subitems': all_subitems,
                                    'inspectors': all_inspectors,
                                    'cycles': all_cycles,
                                    'batches': all_batches})


@approvals_bp.route('/cleanup/edit-defect', methods=['POST'])
@require_team_lead
def cleanup_edit_defect():
    """Edit a single defect description and/or type from cleanup page."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    defect_id = request.form.get('defect_id')
    new_desc = request.form.get('description', '').strip()
    new_type = request.form.get('defect_type', '').strip()
    library_entry_id = request.form.get('library_entry_id')

    if not defect_id or not new_desc:
        abort(400)

    defect = query_db("""
        SELECT d.*, ct.category_name
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        WHERE d.id = ? AND d.tenant_id = ?
    """, [defect_id, tenant_id], one=True)

    if not defect:
        abort(404)

    old_desc = defect['reviewed_comment'] or defect['original_comment']
    old_type = defect['defect_type']

    # Update description
    db.execute("""
        UPDATE defect SET reviewed_comment = ?, updated_at = ? WHERE id = ?
    """, [new_desc, now, defect_id])

    # Update type if changed
    if new_type and new_type != old_type:
        db.execute("""
            UPDATE defect SET defect_type = ?, updated_at = ? WHERE id = ?
        """, [new_type, now, defect_id])
        log_audit(db, tenant_id, 'defect', defect_id, 'type_change',
                  old_value=old_type, new_value=new_type,
                  user_id=session['user_id'], user_name=session['user_name'])

    # Handle library
    if library_entry_id:
        db.execute("""
            UPDATE defect_library SET usage_count = usage_count + 1
            WHERE id = ? AND tenant_id = ?
        """, [library_entry_id, tenant_id])
    else:
        _ensure_in_library(db, tenant_id, defect['item_template_id'],
                           defect['category_name'], new_desc, now)

    # Audit
    if new_desc != old_desc:
        log_audit(db, tenant_id, 'defect', defect_id, 'cleanup_edit',
                  old_value=old_desc, new_value=new_desc,
                  user_id=session['user_id'], user_name=session['user_name'])

    db.commit()

    # Return updated row
    is_htmx = request.headers.get('HX-Request')
    if is_htmx:
        return _render_cleanup_row(defect_id, tenant_id)
    return redirect(url_for('approvals.cleanup'))


@approvals_bp.route('/cleanup/apply-all-preview', methods=['POST'])
@require_team_lead
def cleanup_apply_all_preview():
    """Preview: find all matching defects for bulk update."""
    tenant_id = session['tenant_id']

    old_comment = request.form.get('old_comment', '').strip()
    item_template_id = request.form.get('item_template_id', '').strip()

    # Find all defects with same original_comment + item_template_id
    # on submitted inspections
    matches = [dict(r) for r in query_db("""
        SELECT d.id, d.original_comment, d.reviewed_comment,
               COALESCE(d.reviewed_comment, d.original_comment) AS display_desc,
               u.unit_number, at.area_name, ct.category_name,
               it.item_description
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        JOIN inspection i ON i.unit_id = d.unit_id
            AND i.cycle_id = d.raised_cycle_id AND i.tenant_id = d.tenant_id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND i.status IN ('submitted','reviewed','pending_followup')
        AND d.item_template_id = ?
        AND LOWER(TRIM(COALESCE(d.reviewed_comment, d.original_comment))) = LOWER(TRIM(?))
        ORDER BY u.unit_number
    """, [tenant_id, item_template_id, old_comment])]

    new_desc = request.form.get('new_description', '').strip()
    new_type = request.form.get('new_defect_type', '')
    type_label = 'NI' if new_type == 'not_installed' else 'NTS'
    unit_count = len(set(m['unit_number'] for m in matches))

    html = '<div class="apply-all-list">'
    html += '<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;padding:0.75rem;margin-bottom:1rem;">'
    html += '<p style="margin:0 0 0.5rem;font-weight:700;color:#92400e;">Preview - nothing saved yet</p>'
    html += '<p style="margin:0;font-size:0.85rem;color:#78350f;">'
    html += '<strong>' + str(len(matches)) + '</strong> defect'
    html += ('s' if len(matches) != 1 else '')
    html += ' across <strong>' + str(unit_count) + '</strong> unit'
    html += ('s' if unit_count != 1 else '')
    html += ' will be updated:</p>'
    html += '<p style="margin:0.5rem 0 0;font-size:0.85rem;">'
    html += '<span style="color:#dc2626;text-decoration:line-through;">' + old_comment + '</span>'
    html += ' &#8594; <span style="color:#16a34a;font-weight:600;">' + new_desc + '</span>'
    html += ' <span style="font-size:0.75rem;color:#6b7280;">(' + type_label + ')</span>'
    html += '</p></div>'

    if matches:
        html += '<div style="max-height:300px;overflow-y:auto;border:1px solid #ddd;border-radius:6px;">'
        html += '<table style="width:100%;font-size:0.85rem;border-collapse:collapse;">'
        html += '<thead><tr style="background:#f5f5f5;position:sticky;top:0;">'
        html += '<th style="padding:0.4rem 0.6rem;text-align:left;">Unit</th>'
        html += '<th style="padding:0.4rem 0.6rem;text-align:left;">Area</th>'
        html += '<th style="padding:0.4rem 0.6rem;text-align:left;">Item</th>'
        html += '<th style="padding:0.4rem 0.6rem;text-align:left;">Current</th>'
        html += '</tr></thead><tbody>'
        for m in matches:
            html += '<tr style="border-top:1px solid #eee;">'
            html += '<td style="padding:0.4rem 0.6rem;font-weight:600;">' + m['unit_number'] + '</td>'
            html += '<td style="padding:0.4rem 0.6rem;">' + m['area_name'] + '</td>'
            html += '<td style="padding:0.4rem 0.6rem;">' + m['item_description'] + '</td>'
            html += '<td style="padding:0.4rem 0.6rem;color:#888;">' + (m['display_desc'] or '') + '</td>'
            html += '</tr>'
        html += '</tbody></table></div>'
    else:
        html += '<p style="color:#888;">No other matching defects found.</p>'

    return html


@approvals_bp.route('/cleanup/apply-all-confirm', methods=['POST'])
@require_team_lead
def cleanup_apply_all_confirm():
    """Execute bulk update on all matching defects."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    old_comment = request.form.get('old_comment', '').strip()
    new_desc = request.form.get('new_description', '').strip()
    new_type = request.form.get('new_defect_type', '').strip()
    item_template_id = request.form.get('item_template_id', '').strip()

    if not new_desc or not item_template_id:
        abort(400)

    # Find all matching defects on submitted inspections
    matches = query_db("""
        SELECT d.id, d.original_comment, d.reviewed_comment, d.defect_type,
               d.item_template_id
        FROM defect d
        JOIN inspection i ON i.unit_id = d.unit_id
            AND i.cycle_id = d.raised_cycle_id AND i.tenant_id = d.tenant_id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND i.status IN ('submitted','reviewed','pending_followup')
        AND d.item_template_id = ?
        AND LOWER(TRIM(COALESCE(d.reviewed_comment, d.original_comment))) = LOWER(TRIM(?))
    """, [tenant_id, item_template_id, old_comment])

    count = 0
    for m in matches:
        old = m['reviewed_comment'] or m['original_comment']
        db.execute("""
            UPDATE defect SET reviewed_comment = ?, updated_at = ? WHERE id = ?
        """, [new_desc, now, m['id']])

        if new_type and new_type != m['defect_type']:
            db.execute("""
                UPDATE defect SET defect_type = ?, updated_at = ? WHERE id = ?
            """, [new_type, now, m['id']])

        log_audit(db, tenant_id, 'defect', m['id'], 'cleanup_bulk_edit',
                  old_value=old, new_value=new_desc,
                  user_id=session['user_id'], user_name=session['user_name'])
        count += 1

    # Ensure in library
    cat = query_db("""
        SELECT ct.category_name FROM item_template it
        JOIN category_template ct ON it.category_id = ct.id
        WHERE it.id = ?
    """, [item_template_id], one=True)
    if cat:
        _ensure_in_library(db, tenant_id, item_template_id,
                           cat['category_name'], new_desc, now)

    db.commit()

    # Return confirmation + trigger full page reload
    return ('<div style="padding:1rem;text-align:center;">'
            '<strong style="color:#16a34a;">' + str(count)
            + ' defect' + ('s' if count != 1 else '')
            + ' updated.</strong>'
            ' <a href="' + url_for('approvals.cleanup') + '"'
            ' style="margin-left:1rem;">Refresh page</a></div>')


@approvals_bp.route('/cleanup/delete-defect', methods=['POST'])
@require_team_lead
def cleanup_delete_defect():
    """Delete a single defect and reset its inspection item to OK."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    defect_id = request.form.get('defect_id', '').strip()
    if not defect_id:
        abort(400)

    # Get defect details for audit
    defect = query_db("""
        SELECT d.id, d.unit_id, d.item_template_id, d.raised_cycle_id,
               d.original_comment, d.reviewed_comment,
               COALESCE(d.reviewed_comment, d.original_comment) AS display_desc
        FROM defect d
        WHERE d.id = ? AND d.tenant_id = ?
    """, [defect_id, tenant_id], one=True)

    if not defect:
        abort(404)

    # Delete defect history (FK constraint)
    db.execute("DELETE FROM defect_history WHERE defect_id = ? AND tenant_id = ?",
               [defect_id, tenant_id])

    # Delete the defect
    db.execute("DELETE FROM defect WHERE id = ? AND tenant_id = ?",
               [defect_id, tenant_id])

    # Reset inspection item to OK
    db.execute("""
        UPDATE inspection_item SET status = 'ok', comment = NULL, marked_at = ?
        WHERE item_template_id = ? AND inspection_id IN (
            SELECT i.id FROM inspection i
            WHERE i.unit_id = ? AND i.cycle_id = ? AND i.tenant_id = ?
        )
    """, [now, defect['item_template_id'], defect['unit_id'],
           defect['raised_cycle_id'], tenant_id])

    # Audit trail
    log_audit(db, tenant_id, 'defect', defect_id, 'cleanup_delete',
              old_value=defect['display_desc'], new_value='DELETED',
              user_id=session['user_id'], user_name=session['user_name'])

    db.commit()
    return '', 200




@approvals_bp.route('/cleanup/move-targets', methods=['GET'])
@require_team_lead
def cleanup_move_targets():
    """Return available items in same unit+category for move modal."""
    tenant_id = session['tenant_id']
    defect_id = request.args.get('defect_id', '')
    if not defect_id:
        return ''

    defect = query_db("""
        SELECT d.unit_id, d.item_template_id, d.raised_cycle_id,
               it.category_id
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        WHERE d.id = ? AND d.tenant_id = ?
    """, [defect_id, tenant_id], one=True)
    if not defect:
        return ''

    items = query_db("""
        SELECT it.id, it.item_description,
               pit.item_description AS parent_desc,
               ii.status AS current_status
        FROM item_template it
        LEFT JOIN item_template pit ON it.parent_item_id = pit.id
        LEFT JOIN inspection_item ii ON ii.item_template_id = it.id
            AND ii.inspection_id = (
                SELECT i.id FROM inspection i
                WHERE i.unit_id = ? AND i.cycle_id = ?
                AND i.tenant_id = ? ORDER BY i.created_at DESC LIMIT 1)
        WHERE it.category_id = ? AND it.tenant_id = ?
        AND it.id != ?
        ORDER BY it.item_order
    """, [defect['unit_id'], defect['raised_cycle_id'], tenant_id,
           defect['category_id'], tenant_id, defect['item_template_id']])

    html = ''
    for it in items:
        path = (it['parent_desc'] + ' > ' + it['item_description']) if it['parent_desc'] else it['item_description']
        st = it['current_status'] or 'pending'
        badge = 'ok' if st == 'ok' else ('nts' if st in ('not_to_standard', 'not_installed') else '')
        html += '<div class="move-item" data-tid="' + it['id'] + '" '
        html += 'style="padding:0.5rem 0.75rem;cursor:pointer;border-bottom:1px solid #f3f4f6;'
        html += 'display:flex;justify-content:space-between;align-items:center;font-size:0.85rem;">'
        html += '<span>' + path + '</span>'
        html += '<span style="font-size:0.7rem;color:#9ca3af;">' + st.replace('_', ' ') + '</span>'
        html += '</div>'
    if not items:
        html = '<div style="padding:0.75rem;color:#9ca3af;font-size:0.85rem;">No other items in this category</div>'
    return html


@approvals_bp.route('/cleanup/move-defect', methods=['POST'])
@require_team_lead
def cleanup_move_defect():
    """Move a defect from one item to another within same unit+category."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    defect_id = request.form.get('defect_id', '').strip()
    target_template_id = request.form.get('target_template_id', '').strip()
    if not defect_id or not target_template_id:
        abort(400)

    defect = query_db("""
        SELECT d.id, d.unit_id, d.item_template_id, d.raised_cycle_id,
               d.defect_type, d.original_comment, d.reviewed_comment,
               COALESCE(d.reviewed_comment, d.original_comment) AS display_desc
        FROM defect d
        WHERE d.id = ? AND d.tenant_id = ?
    """, [defect_id, tenant_id], one=True)
    if not defect:
        abort(404)

    old_template = defect['item_template_id']
    insp = query_db("""
        SELECT id FROM inspection
        WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?
        ORDER BY created_at DESC LIMIT 1
    """, [defect['unit_id'], defect['raised_cycle_id'], tenant_id], one=True)
    if not insp:
        abort(404)

    # 1. Update defect to target item
    db.execute("""
        UPDATE defect SET item_template_id = ?, updated_at = ?
        WHERE id = ? AND tenant_id = ?
    """, [target_template_id, now, defect_id, tenant_id])

    # 2. Reset source inspection_item to OK
    db.execute("""
        UPDATE inspection_item SET status = 'ok', comment = NULL, marked_at = ?
        WHERE inspection_id = ? AND item_template_id = ? AND tenant_id = ?
    """, [now, insp['id'], old_template, tenant_id])

    # 3. Mark target inspection_item
    item_status = 'not_installed' if defect['defect_type'] == 'not_installed' else 'not_to_standard'
    db.execute("""
        UPDATE inspection_item SET status = ?, comment = ?, marked_at = ?
        WHERE inspection_id = ? AND item_template_id = ? AND tenant_id = ?
    """, [item_status, defect['display_desc'], now, insp['id'], target_template_id, tenant_id])

    # 4. Audit
    log_audit(db, tenant_id, 'defect', defect_id, 'cleanup_move',
              old_value='item:' + old_template,
              new_value='item:' + target_template_id,
              user_id=session['user_id'], user_name=session['user_name'])

    db.commit()
    return '', 200


@approvals_bp.route('/cleanup/exclude-preview', methods=['GET'])
@require_team_lead
def cleanup_exclude_preview():
    """Preview impact of excluding an item from a batch."""
    import json
    tenant_id = session['tenant_id']
    item_template_id = request.args.get('item_template_id', '')
    batch_id = request.args.get('batch_id', '')

    if not item_template_id or not batch_id:
        return json.dumps({'error': 'Missing params'}), 400, {'Content-Type': 'application/json'}

    # Get all unit_ids in this batch
    batch_units = query_db("""
        SELECT DISTINCT bu.unit_id, u.unit_number
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        WHERE bu.batch_id = ? AND bu.status != 'removed' AND bu.tenant_id = ?
    """, [batch_id, tenant_id])

    unit_ids = [bu['unit_id'] for bu in batch_units]
    if not unit_ids:
        return json.dumps({'defect_count': 0, 'unit_count': 0, 'unit_numbers': []}), 200, {'Content-Type': 'application/json'}

    placeholders = ','.join(['?'] * len(unit_ids))
    defects = query_db(f"""
        SELECT d.id, d.unit_id, u.unit_number
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        WHERE d.item_template_id = ? AND d.status = 'open'
        AND d.unit_id IN ({placeholders})
        AND d.tenant_id = ?
    """, [item_template_id] + unit_ids + [tenant_id])

    affected_units = sorted(set(d['unit_number'] for d in defects))

    return json.dumps({
        'defect_count': len(defects),
        'unit_count': len(affected_units),
        'unit_numbers': affected_units
    }), 200, {'Content-Type': 'application/json'}


@approvals_bp.route('/cleanup/exclude-item', methods=['POST'])
@require_team_lead
def cleanup_exclude_item():
    """Exclude an item from all units in a batch."""
    import json
    import uuid
    tenant_id = session['tenant_id']
    item_template_id = request.form.get('item_template_id', '')
    batch_id = request.form.get('batch_id', '')

    if not item_template_id or not batch_id:
        abort(400)

    db = get_db()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    # Get all units and cycles in this batch
    batch_units = query_db("""
        SELECT DISTINCT bu.unit_id, bu.cycle_id
        FROM batch_unit bu
        WHERE bu.batch_id = ? AND bu.status != 'removed' AND bu.tenant_id = ?
    """, [batch_id, tenant_id])

    if not batch_units:
        abort(404)

    unit_ids = [bu['unit_id'] for bu in batch_units]
    cycle_ids = set(bu['cycle_id'] for bu in batch_units)

    # Find all open defects with this item_template_id across batch units
    placeholders = ','.join(['?'] * len(unit_ids))
    defects = query_db(f"""
        SELECT d.id, d.unit_id, d.raised_cycle_id,
               COALESCE(d.reviewed_comment, d.original_comment) AS desc
        FROM defect d
        WHERE d.item_template_id = ? AND d.status = 'open'
        AND d.unit_id IN ({placeholders})
        AND d.tenant_id = ?
    """, [item_template_id] + unit_ids + [tenant_id])

    deleted_count = 0
    for defect in defects:
        db.execute("DELETE FROM defect_history WHERE defect_id = ? AND tenant_id = ?",
                   [defect['id'], tenant_id])
        db.execute("DELETE FROM defect WHERE id = ? AND tenant_id = ?",
                   [defect['id'], tenant_id])
        deleted_count += 1

    # Reset inspection_items to skipped
    for bu in batch_units:
        db.execute("""
            UPDATE inspection_item SET status = 'skipped', comment = NULL, marked_at = ?
            WHERE item_template_id = ? AND inspection_id IN (
                SELECT i.id FROM inspection i
                WHERE i.unit_id = ? AND i.cycle_id = ? AND i.tenant_id = ?
            )
        """, [now, item_template_id, bu['unit_id'], bu['cycle_id'], tenant_id])

    # Add to cycle_excluded_item for each cycle
    excl_added = 0
    for cid in cycle_ids:
        existing = query_db("""
            SELECT id FROM cycle_excluded_item
            WHERE cycle_id = ? AND item_template_id = ? AND tenant_id = ?
        """, [cid, item_template_id, tenant_id], one=True)
        if not existing:
            excl_id = uuid.uuid4().hex[:8]
            db.execute("""
                INSERT INTO cycle_excluded_item
                (id, tenant_id, cycle_id, item_template_id, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [excl_id, tenant_id, cid, item_template_id,
                  'Excluded via cleanup', now])
            excl_added += 1

    log_audit(db, tenant_id, 'item_template', item_template_id, 'cleanup_exclude',
              old_value=f'{deleted_count} defects removed',
              new_value=f'Excluded from batch {batch_id} ({excl_added} cycles)',
              user_id=session['user_id'], user_name=session['user_name'])

    db.commit()
    return json.dumps({'deleted': deleted_count, 'cycles': len(cycle_ids)}), 200, {'Content-Type': 'application/json'}

@approvals_bp.route('/cleanup/suggestions', methods=['GET'])
@require_team_lead
def cleanup_suggestions():
    """HTMX: return library suggestions for a given item_template_id."""
    tenant_id = session['tenant_id']
    item_template_id = request.args.get('item_template_id', '')
    query_text = request.args.get('q', '').strip().lower()

    if not item_template_id:
        return ''

    # Get category for this item
    cat = query_db("""
        SELECT ct.category_name FROM item_template it
        JOIN category_template ct ON it.category_id = ct.id
        WHERE it.id = ? AND it.tenant_id = ?
    """, [item_template_id, tenant_id], one=True)

    if not cat:
        return ''

    # Item-specific entries first, then category-level
    entries = [dict(r) for r in query_db("""
        SELECT id, description, usage_count,
            CASE WHEN item_template_id = ? THEN 1 ELSE 0 END AS is_item_specific
        FROM defect_library
        WHERE tenant_id = ? AND (item_template_id = ? OR
            (item_template_id IS NULL AND category_name = ?))
        ORDER BY is_item_specific DESC, usage_count DESC
    """, [item_template_id, tenant_id, item_template_id, cat['category_name']])]

    # Filter by query text if provided
    if query_text:
        entries = [e for e in entries if query_text in e['description'].lower()]

    if not entries:
        return '<div class="sugg-empty">No suggestions found</div>'

    html = ''
    for e in entries[:15]:
        html += ('<div class="sugg-item" '
                 'data-lib-id="' + e['id'] + '" '
                 'data-desc="' + e['description'].replace('"', '&quot;') + '">'
                 + e['description']
                 + '<span class="sugg-count">' + str(e['usage_count']) + 'x</span>'
                 + '</div>')
    return html


def _ensure_in_library(db, tenant_id, item_template_id, category_name,
                       description, now):
    """Add description to library if not already present (0.95 match)."""
    existing = query_db("""
        SELECT id, description FROM defect_library
        WHERE tenant_id = ? AND item_template_id = ?
    """, [tenant_id, item_template_id])

    for entry in existing:
        score = SequenceMatcher(
            None, description.lower(), entry['description'].lower()).ratio()
        if score >= 0.95:
            db.execute("""
                UPDATE defect_library SET usage_count = usage_count + 1
                WHERE id = ?
            """, [entry['id']])
            return

    # Also check category-level
    cat_entries = query_db("""
        SELECT id, description FROM defect_library
        WHERE tenant_id = ? AND category_name = ? AND item_template_id IS NULL
    """, [tenant_id, category_name])

    for entry in cat_entries:
        score = SequenceMatcher(
            None, description.lower(), entry['description'].lower()).ratio()
        if score >= 0.95:
            db.execute("""
                UPDATE defect_library SET usage_count = usage_count + 1
                WHERE id = ?
            """, [entry['id']])
            return

    # New entry
    lib_id = generate_id()
    db.execute("""
        INSERT INTO defect_library
        (id, tenant_id, category_name, item_template_id,
         description, usage_count, is_system, created_at)
        VALUES (?, ?, ?, ?, ?, 1, 0, ?)
    """, [lib_id, tenant_id, category_name, item_template_id, description, now])


def _render_cleanup_row(defect_id, tenant_id):
    """Render a single cleanup table row after edit."""
    d = query_db("""
        SELECT d.id, d.unit_id, d.item_template_id,
               d.original_comment, d.reviewed_comment,
               COALESCE(d.reviewed_comment, d.original_comment) AS display_desc,
               d.defect_type, d.raised_cycle_id,
               u.unit_number, i.inspector_name,
               it.item_description,
               parent.item_description AS parent_description,
               ct.category_name, at.area_name
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        JOIN inspection i ON i.unit_id = d.unit_id
            AND i.cycle_id = d.raised_cycle_id AND i.tenant_id = d.tenant_id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        LEFT JOIN item_template parent ON it.parent_item_id = parent.id
        WHERE d.id = ? AND d.tenant_id = ?
    """, [defect_id, tenant_id], one=True)

    if not d:
        return ''

    d = dict(d)
    if d['parent_description']:
        d['item_path'] = d['parent_description'] + ' > ' + d['item_description']
    else:
        d['item_path'] = d['item_description']

    # Check if now clean
    lib_check = query_db("""
        SELECT 1 FROM defect_library
        WHERE tenant_id = ? AND category_name = ?
        AND LOWER(TRIM(description)) = LOWER(TRIM(?))
        LIMIT 1
    """, [tenant_id, d['category_name'], d['display_desc']])

    status_class = 'clean' if lib_check else 'new'
    status_label = 'Clean' if lib_check else 'New'
    type_label = 'NI' if d['defect_type'] == 'not_installed' else 'NTS'
    type_class = 'ni' if d['defect_type'] == 'not_installed' else 'nts'

    return (
        '<tr id="row-' + d['id'] + '" class="cleanup-row status-' + status_class + '">'
        '<td class="col-unit">' + d['unit_number'] + '</td>'
        '<td class="col-area">' + d['area_name'] + '</td>'
        '<td class="col-cat">' + d['category_name'] + '</td>'
        '<td class="col-item">' + d['item_path'] + '</td>'
        '<td class="col-desc">'
        '<span class="desc-text">' + (d['display_desc'] or '') + '</span>'
        '</td>'
        '<td class="col-type"><span class="type-badge ' + type_class + '">'
        + type_label + '</span></td>'
        '<td class="col-status"><span class="status-badge ' + status_class + '">'
        + status_label + '</span></td>'
        '<td class="col-actions">'
        '<button class="btn-edit" onclick="startEdit(this)" '
        'data-id="' + d['id'] + '" '
        'data-template="' + d['item_template_id'] + '" '
        'data-desc="' + (d['display_desc'] or '').replace('"', '&quot;') + '" '
        'data-type="' + d['defect_type'] + '">'
        'Edit</button>'
        '</td>'
        '</tr>'
    )
