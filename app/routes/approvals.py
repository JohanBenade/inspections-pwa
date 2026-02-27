"""
Approvals routes - Kevin's command centre.
Review defect descriptions, mark units reviewed, sign off cycles, push PDFs.
Roles: manager + admin only.
"""
import os
import base64
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from difflib import SequenceMatcher
from collections import OrderedDict
from flask import (Blueprint, render_template, session, redirect,
                   url_for, abort, request, flash)
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
             FROM inspection i WHERE i.cycle_id = ic.id AND i.status = 'reviewed') AS reviewed_count,
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
        WHERE d.raised_cycle_id = ? AND d.status = 'open' AND d.tenant_id = ?
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
               at.area_name, at.area_order, ct.category_order, it.item_order
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        LEFT JOIN item_template parent ON it.parent_item_id = parent.id
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
    for d in defects:
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
    cycles = _get_cycle_pipeline(tenant_id)
    return render_template('approvals/pipeline.html', cycles=cycles)


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
    return redirect(url_for('approvals.review', cycle_id=cycle_id))


@approvals_bp.route('/<cycle_id>/push-pdfs', methods=['POST'])
@require_manager
def push_pdfs(cycle_id):
    """Generate and push PDFs to SharePoint via Make webhook."""
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
        flash('Cycle must be signed off before pushing PDFs.', 'error')
        return redirect(url_for('approvals.review', cycle_id=cycle_id))

    if cycle['pdfs_pushed_at']:
        flash('PDFs have already been pushed for this cycle.', 'error')
        return redirect(url_for('approvals.review', cycle_id=cycle_id))

    webhook_url = os.environ.get('MAKE_WEBHOOK_URL', '')
    if not webhook_url:
        flash('Make webhook URL not configured. Set MAKE_WEBHOOK_URL in Render.', 'error')
        return redirect(url_for('approvals.review', cycle_id=cycle_id))

    # Get all units in this cycle
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

    floor_names = {0: 'Ground Floor', 1: '1st Floor', 2: '2nd Floor', 3: '3rd Floor'}
    success_count = 0
    fail_count = 0
    errors = []

    for unit in units:
        try:
            pdf_bytes = generate_defects_pdf(tenant_id, unit['id'], cycle_id)
            if not pdf_bytes:
                errors.append('Unit {}: PDF generation failed'.format(unit['unit_number']))
                fail_count += 1
                continue

            filename = generate_pdf_filename(
                unit, dict(cycle),
                inspection_date=unit.get('inspection_date'))

            payload = json.dumps({
                'filename': filename,
                'unit_number': unit['unit_number'],
                'block': unit.get('block', ''),
                'floor': floor_names.get(unit.get('floor'), ''),
                'cycle_number': cycle['cycle_number'],
                'cycle_id': cycle_id,
                'pdf_base64': base64.b64encode(pdf_bytes).decode('ascii')
            }).encode('utf-8')

            req = urllib.request.Request(
                webhook_url, data=payload,
                headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status in (200, 201, 202):
                    success_count += 1
                else:
                    errors.append('Unit {}: HTTP {}'.format(
                        unit['unit_number'], resp.status))
                    fail_count += 1

        except urllib.error.URLError as e:
            errors.append('Unit {}: {}'.format(
                unit['unit_number'], str(e)[:100]))
            fail_count += 1
        except Exception as e:
            errors.append('Unit {}: {}'.format(
                unit['unit_number'], str(e)[:100]))
            fail_count += 1

    # Update cycle status
    if success_count > 0:
        push_status = 'complete' if fail_count == 0 else 'partial'
        db.execute("""
            UPDATE inspection_cycle
            SET pdfs_pushed_at = ?, pdfs_push_status = ?
            WHERE id = ?
        """, [now, push_status, cycle_id])

        log_audit(db, tenant_id, 'cycle', cycle_id, 'pdfs_pushed',
                  new_value='{}/{} PDFs pushed'.format(
                      success_count, success_count + fail_count),
                  user_id=session['user_id'], user_name=session['user_name'])

        db.commit()

    block = cycle['block'] or 'Cycle'
    if fail_count == 0:
        flash('{} PDFs pushed to SharePoint for {}.'.format(
            success_count, block), 'success')
    elif success_count > 0:
        flash('{} PDFs pushed, {} failed for {}. {}'.format(
            success_count, fail_count, block,
            '; '.join(errors[:3])), 'error')
    else:
        flash('All {} PDFs failed for {}. {}'.format(
            fail_count, block,
            errors[0] if errors else 'Unknown'), 'error')

    return redirect(url_for('approvals.review', cycle_id=cycle_id))


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

    # All defects on submitted inspections
    defects = [dict(r) for r in query_db("""
        SELECT d.id, d.unit_id, d.item_template_id,
               d.original_comment, d.reviewed_comment,
               COALESCE(d.reviewed_comment, d.original_comment) AS display_desc,
               d.defect_type, d.raised_cycle_id, d.created_at,
               u.unit_number, u.block, u.floor,
               i.inspector_name, i.status AS insp_status,
               it.item_description,
               parent.item_description AS parent_description,
               ct.category_name, ct.id AS category_id,
               at.area_name, at.area_order, ct.category_order, it.item_order,
               ic.cycle_number, ic.block AS cycle_block, ic.floor AS cycle_floor
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        JOIN inspection i ON i.unit_id = d.unit_id
            AND i.cycle_id = d.raised_cycle_id AND i.tenant_id = d.tenant_id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
        LEFT JOIN item_template parent ON it.parent_item_id = parent.id
        WHERE d.status = 'open' AND d.tenant_id = ?
        AND i.status = 'submitted'
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
    placeholders = {'defect noted', 'n/a', 'na', 'as indicated', ''}
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
    if f_status:
        filtered = [d for d in filtered if d['cleanup_status'] == f_status]
    if f_inspector:
        filtered = [d for d in filtered if d['inspector_name'] == f_inspector]
    if f_cycle:
        filtered = [d for d in filtered if d['cycle_label'] == f_cycle]

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

    return render_template('approvals/cleanup.html',
                           defects=filtered, stats=stats,
                           filters={'unit': f_unit, 'area': f_area,
                                    'category': f_category, 'item': f_item,
                                    'subitem': f_subitem, 'status': f_status,
                                    'inspector': f_inspector, 'cycle': f_cycle},
                           options={'units': all_units, 'areas': all_areas,
                                    'categories': all_categories,
                                    'item_names': all_items,
                                    'subitems': all_subitems,
                                    'inspectors': all_inspectors,
                                    'cycles': all_cycles})


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

    source_id = request.form.get('defect_id')
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
        AND i.status = 'submitted'
        AND d.item_template_id = ?
        AND LOWER(TRIM(COALESCE(d.reviewed_comment, d.original_comment))) = LOWER(TRIM(?))
        AND d.id != ?
        ORDER BY u.unit_number
    """, [tenant_id, item_template_id, old_comment, source_id])]

    html = '<div class="apply-all-list">'
    html += '<p style="margin-bottom:0.75rem;font-weight:600;">'
    html += 'This will update <strong>' + str(len(matches))
    html += ' defect' + ('s' if len(matches) != 1 else '')
    html += '</strong> across <strong>'
    html += str(len(set(m['unit_number'] for m in matches)))
    html += ' unit' + ('s' if len(set(m['unit_number'] for m in matches)) != 1 else '')
    html += '</strong></p>'

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
        AND i.status = 'submitted'
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
