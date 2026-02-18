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
from app.auth import require_manager
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
             AND d.tenant_id = ic.tenant_id) AS defect_count
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

    stats = {
        'total': len(inspections),
        'reviewed': total_reviewed,
        'defects': len(defects),
        'to_fix': total_to_fix,
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
