"""
Data Quality Console - Admin power tools for defect description management.
Tab 1: Description Health (singletons, long, vague, clusters)
Tab 2: Structural Checks (future)
Tab 3: Library Audit (future)
Access: Admin only (Johan).
"""
from flask import Blueprint, render_template, session, request
from app.auth import require_admin
from app.services.db import query_db, get_db

data_quality_bp = Blueprint('data_quality', __name__, url_prefix='/data-quality')

# Vague patterns that tell Raubex nothing useful
VAGUE_PATTERNS = [
    'as indicated',
    'not done well',
    'not done properly',
    'needs attention',
    'not acceptable',
    'defective',
]

# Character threshold for "long" descriptions
LONG_THRESHOLD = 50


@data_quality_bp.route('/')
@require_admin
def index():
    """Redirect to descriptions tab."""
    return descriptions()


@data_quality_bp.route('/descriptions')
@require_admin
def descriptions():
    """Tab 1: Description Health - KPI cards + singleton/long/vague tables."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    # ── KPI Cards ──────────────────────────────────────────
    unique_count = dict(query_db(
        "SELECT COUNT(DISTINCT original_comment) AS cnt "
        "FROM defect WHERE status='open' AND tenant_id=?",
        (tenant_id,), one=True
    ))['cnt']

    singleton_count = dict(query_db(
        "SELECT COUNT(*) AS cnt FROM ("
        "  SELECT original_comment FROM defect "
        "  WHERE status='open' AND tenant_id=? "
        "  GROUP BY original_comment HAVING COUNT(*)=1"
        ")",
        (tenant_id,), one=True
    ))['cnt']

    avg_length = dict(query_db(
        "SELECT ROUND(AVG(LENGTH(original_comment)),1) AS avg_len "
        "FROM defect WHERE status='open' AND tenant_id=? "
        "AND original_comment IS NOT NULL",
        (tenant_id,), one=True
    ))['avg_len'] or 0

    # Vague count - build WHERE clause from patterns
    vague_clauses = " OR ".join(
        ["original_comment LIKE ?"] * len(VAGUE_PATTERNS)
    )
    vague_params = [tenant_id] + ['%' + p + '%' for p in VAGUE_PATTERNS]
    vague_count = dict(query_db(
        "SELECT COUNT(DISTINCT original_comment) AS cnt "
        "FROM defect WHERE status='open' AND tenant_id=? "
        "AND (" + vague_clauses + ")",
        vague_params, one=True
    ))['cnt']

    kpis = {
        'unique': unique_count,
        'singletons': singleton_count,
        'avg_length': avg_length,
        'vague': vague_count,
    }

    # ── Section 1A: Singletons ─────────────────────────────
    singletons_raw = query_db(
        "SELECT d.original_comment, d.id AS defect_id, "
        "  u.unit_number, at2.area_name, ct.category_name, "
        "  LENGTH(d.original_comment) AS char_len "
        "FROM defect d "
        "JOIN unit u ON d.unit_id = u.id "
        "JOIN item_template it ON d.item_template_id = it.id "
        "JOIN category_template ct ON it.category_id = ct.id "
        "JOIN area_template at2 ON ct.area_id = at2.id "
        "WHERE d.status='open' AND d.tenant_id=? "
        "AND d.original_comment IN ("
        "  SELECT original_comment FROM defect "
        "  WHERE status='open' AND tenant_id=? "
        "  GROUP BY original_comment HAVING COUNT(*)=1"
        ") "
        "ORDER BY LENGTH(d.original_comment) DESC",
        (tenant_id, tenant_id)
    )
    singletons = [dict(r) for r in singletons_raw]

    # ── Section 1B: Long Descriptions ──────────────────────
    long_raw = query_db(
        "SELECT original_comment, COUNT(*) AS usage, "
        "  LENGTH(original_comment) AS char_len "
        "FROM defect "
        "WHERE status='open' AND tenant_id=? "
        "AND original_comment IS NOT NULL "
        "GROUP BY original_comment "
        "HAVING char_len > ? "
        "ORDER BY char_len DESC",
        (tenant_id, LONG_THRESHOLD)
    )
    long_descs = [dict(r) for r in long_raw]

    # ── Section 1C: Vague Descriptions ─────────────────────
    vague_raw = query_db(
        "SELECT original_comment, COUNT(*) AS usage "
        "FROM defect "
        "WHERE status='open' AND tenant_id=? "
        "AND (" + vague_clauses + ") "
        "GROUP BY original_comment "
        "ORDER BY usage DESC",
        vague_params
    )
    vague_descs = [dict(r) for r in vague_raw]

    # ── Merge target list (top descriptions by usage) ──────
    # Used by merge dropdowns - top 50 descriptions
    merge_targets_raw = query_db(
        "SELECT original_comment, COUNT(*) AS usage "
        "FROM defect "
        "WHERE status='open' AND tenant_id=? "
        "AND original_comment IS NOT NULL "
        "GROUP BY original_comment "
        "ORDER BY usage DESC "
        "LIMIT 50",
        (tenant_id,)
    )
    merge_targets = [dict(r) for r in merge_targets_raw]

    return render_template('data_quality/descriptions.html',
                           kpis=kpis,
                           singletons=singletons,
                           long_descs=long_descs,
                           vague_descs=vague_descs,
                           merge_targets=merge_targets,
                           vague_patterns=VAGUE_PATTERNS,
                           long_threshold=LONG_THRESHOLD)


@data_quality_bp.route('/merge', methods=['POST'])
@require_admin
def merge_description():
    """Merge one description into another across all open defects."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    old_desc = request.form.get('old_description', '').strip()
    new_desc = request.form.get('new_description', '').strip()

    if not old_desc or not new_desc:
        return ('<tr class="bg-red-50"><td colspan="5" class="px-4 py-3 text-sm text-red-600">'
                'Both descriptions required.</td></tr>')

    if old_desc == new_desc:
        return ('<tr class="bg-amber-50"><td colspan="5" class="px-4 py-3 text-sm text-amber-600">'
                'Descriptions are identical.</td></tr>')

    db = get_db()

    # Count affected defects
    count_row = db.execute(
        "SELECT COUNT(*) AS cnt FROM defect "
        "WHERE original_comment=? AND status='open' AND tenant_id=?",
        (old_desc, tenant_id)
    ).fetchone()
    affected = count_row[0] if count_row else 0

    if affected == 0:
        return ('<tr class="bg-amber-50"><td colspan="5" class="px-4 py-3 text-sm text-amber-600">'
                'No defects found with that description.</td></tr>')

    # Update defects
    db.execute(
        "UPDATE defect SET original_comment=?, updated_at=CURRENT_TIMESTAMP "
        "WHERE original_comment=? AND status='open' AND tenant_id=?",
        (new_desc, old_desc, tenant_id)
    )

    # Update defect library: increment target, deactivate source
    db.execute(
        "UPDATE defect_library SET usage_count = usage_count + ? "
        "WHERE description=? AND tenant_id=?",
        (affected, new_desc, tenant_id)
    )
    db.execute(
        "UPDATE defect_library SET usage_count = 0 "
        "WHERE description=? AND tenant_id=?",
        (old_desc, tenant_id)
    )

    db.commit()

    return (
        '<tr class="bg-green-50">'
        '<td colspan="5" class="px-4 py-3 text-sm text-green-700">'
        '<strong>Merged.</strong> {} defect{} updated: '
        '<span class="line-through text-gray-400">{}</span> '
        '&rarr; <strong>{}</strong>'
        '</td></tr>'
    ).format(affected, 's' if affected != 1 else '', old_desc, new_desc)


@data_quality_bp.route('/edit', methods=['POST'])
@require_admin
def edit_description():
    """Edit a single defect description (and update library)."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    old_desc = request.form.get('old_description', '').strip()
    new_desc = request.form.get('new_description', '').strip()

    if not old_desc or not new_desc:
        return ('<tr class="bg-red-50"><td colspan="5" class="px-4 py-3 text-sm text-red-600">'
                'Description cannot be empty.</td></tr>')

    if old_desc == new_desc:
        return ('<tr class="bg-amber-50"><td colspan="5" class="px-4 py-3 text-sm text-amber-600">'
                'No change detected.</td></tr>')

    db = get_db()

    # Count affected
    count_row = db.execute(
        "SELECT COUNT(*) AS cnt FROM defect "
        "WHERE original_comment=? AND status='open' AND tenant_id=?",
        (old_desc, tenant_id)
    ).fetchone()
    affected = count_row[0] if count_row else 0

    # Update all defects with this description
    db.execute(
        "UPDATE defect SET original_comment=?, updated_at=CURRENT_TIMESTAMP "
        "WHERE original_comment=? AND status='open' AND tenant_id=?",
        (new_desc, old_desc, tenant_id)
    )

    # Update library entry
    db.execute(
        "UPDATE defect_library SET description=? "
        "WHERE description=? AND tenant_id=?",
        (new_desc, old_desc, tenant_id)
    )

    db.commit()

    return (
        '<tr class="bg-green-50">'
        '<td colspan="5" class="px-4 py-3 text-sm text-green-700">'
        '<strong>Updated.</strong> {} defect{}: '
        '<span class="line-through text-gray-400">{}</span> '
        '&rarr; <strong>{}</strong>'
        '</td></tr>'
    ).format(affected, 's' if affected != 1 else '', old_desc, new_desc)


