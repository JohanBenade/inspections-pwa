"""
Data Quality Console - Admin power tools for defect description management.
Tab 1: Description Health (singletons, long, vague, clusters)
Tab 2: Structural Checks (mismatches, duplicates, orphans, wash sync)
Tab 3: Library Audit (overview, dead entries, merges, orphans)
Access: Admin only (Johan).
"""
from flask import Blueprint, render_template, session, request
from app.auth import require_admin
from app.services.db import query_db, get_db
from difflib import SequenceMatcher

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

# Similarity threshold for clustering (0.8 = tight matches only)
CLUSTER_THRESHOLD = 0.8


def _compute_clusters(descriptions):
    """
    Group similar descriptions into clusters using complete-linkage matching.
    Every member in a cluster must be >= threshold similar to every other member.
    This prevents transitive chaining (A~B, B~C does NOT put A+C together
    unless A~C also holds).

    Scoped by category to limit comparison space.

    Input: list of dicts with original_comment, usage, category_name
    Output: list of cluster dicts sorted by total_usage desc
    """
    # Group by category
    by_category = {}
    for d in descriptions:
        cat = d['category_name']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(d)

    # Build lookup: description -> {usage, category}
    desc_info = {}
    for d in descriptions:
        key = d['original_comment']
        if key not in desc_info:
            desc_info[key] = {'usage': d['usage'], 'category': d['category_name']}
        else:
            desc_info[key]['usage'] += d['usage']

    # Pre-compute similarity scores within each category, store edges
    edges = {}  # (a, b) -> score, where a < b alphabetically
    for cat, members in by_category.items():
        descs_in_cat = list(set(m['original_comment'] for m in members))
        n = len(descs_in_cat)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = descs_in_cat[i], descs_in_cat[j]
                score = SequenceMatcher(
                    None, a.lower().strip(), b.lower().strip()
                ).ratio()
                if score >= CLUSTER_THRESHOLD:
                    key = (min(a, b), max(a, b))
                    edges[key] = score

    def are_all_similar(group, candidate):
        """Check if candidate is >= threshold similar to ALL members of group."""
        for member in group:
            key = (min(member, candidate), max(member, candidate))
            if key not in edges:
                return False
        return True

    # Build clusters using complete-linkage greedy approach
    # Start with highest-similarity pairs, try to grow each cluster
    clustered = set()
    clusters_raw = []

    # Sort edges by score desc so we start with strongest matches
    sorted_edges = sorted(edges.items(), key=lambda x: x[1], reverse=True)

    for (a, b), score in sorted_edges:
        if a in clustered or b in clustered:
            continue
        # Start a new cluster with this pair
        cluster = [a, b]
        clustered.add(a)
        clustered.add(b)

        # Try to grow: find unclustered descriptions similar to ALL current members
        # Get category for this cluster
        cat = desc_info[a]['category']
        if cat in by_category:
            candidates = [
                m['original_comment'] for m in by_category[cat]
                if m['original_comment'] not in clustered
            ]
            for c in candidates:
                if are_all_similar(cluster, c):
                    cluster.append(c)
                    clustered.add(c)

        if len(cluster) >= 2:
            clusters_raw.append(cluster)

    # Build output
    clusters = []
    for members in clusters_raw:
        member_list = []
        total = 0
        cat = desc_info[members[0]]['category']
        for m in members:
            usage = desc_info[m]['usage']
            member_list.append({'description': m, 'usage': usage})
            total += usage
        member_list.sort(key=lambda x: x['usage'], reverse=True)
        clusters.append({
            'category': cat,
            'members': member_list,
            'total_usage': total,
            'suggested_canonical': member_list[0]['description'],
            'member_count': len(member_list),
        })

    clusters.sort(key=lambda x: x['total_usage'], reverse=True)
    return clusters


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

    # ── Section 1D: Description Clusters ───────────────────
    # Group similar descriptions within same category using fuzzy matching
    cluster_raw = query_db(
        "SELECT d.original_comment, COUNT(*) AS usage, "
        "  ct.category_name "
        "FROM defect d "
        "JOIN item_template it ON d.item_template_id = it.id "
        "JOIN category_template ct ON it.category_id = ct.id "
        "WHERE d.status='open' AND d.tenant_id=? "
        "AND d.original_comment IS NOT NULL "
        "GROUP BY d.original_comment, ct.category_name "
        "ORDER BY ct.category_name, usage DESC",
        (tenant_id,)
    )
    cluster_descs = [dict(r) for r in cluster_raw]

    clusters = _compute_clusters(cluster_descs)

    return render_template('data_quality/descriptions.html',
                           kpis=kpis,
                           singletons=singletons,
                           long_descs=long_descs,
                           vague_descs=vague_descs,
                           merge_targets=merge_targets,
                           clusters=clusters,
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


@data_quality_bp.route('/merge-cluster', methods=['POST'])
@require_admin
def merge_cluster():
    """Merge all cluster members into the canonical description."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    canonical = request.form.get('canonical', '').strip()
    members = request.form.getlist('members')

    if not canonical or len(members) < 2:
        return ('<div class="border border-red-200 rounded-lg p-4 text-sm text-red-600">'
                'Invalid cluster data.</div>')

    # Remove canonical from merge sources
    sources = [m.strip() for m in members if m.strip() != canonical]
    if not sources:
        return ('<div class="border border-amber-200 rounded-lg p-4 text-sm text-amber-600">'
                'Nothing to merge &mdash; all members match the canonical.</div>')

    db = get_db()
    total_affected = 0

    for old_desc in sources:
        if not old_desc:
            continue

        count_row = db.execute(
            "SELECT COUNT(*) FROM defect "
            "WHERE original_comment=? AND status='open' AND tenant_id=?",
            (old_desc, tenant_id)
        ).fetchone()
        affected = count_row[0] if count_row else 0

        if affected > 0:
            db.execute(
                "UPDATE defect SET original_comment=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE original_comment=? AND status='open' AND tenant_id=?",
                (canonical, old_desc, tenant_id)
            )
            db.execute(
                "UPDATE defect_library SET usage_count = usage_count + ? "
                "WHERE description=? AND tenant_id=?",
                (affected, canonical, tenant_id)
            )
            db.execute(
                "UPDATE defect_library SET usage_count = 0 "
                "WHERE description=? AND tenant_id=?",
                (old_desc, tenant_id)
            )
            total_affected += affected

    db.commit()

    merged_list = ', '.join(
        '<span class="line-through text-gray-400">{}</span>'.format(s)
        for s in sources
    )

    return (
        '<div class="border border-green-200 bg-green-50 rounded-lg p-4 text-sm text-green-700">'
        '<strong>Cluster merged.</strong> {} defect{} updated across {} description{}. '
        'All now read: <strong>{}</strong><br>'
        '<span class="text-xs text-gray-500 mt-1 block">Removed: {}</span>'
        '</div>'
    ).format(
        total_affected,
        's' if total_affected != 1 else '',
        len(sources),
        's' if len(sources) != 1 else '',
        canonical,
        merged_list
    )


# ═══════════════════════════════════════════════════════════════════
# TAB 2: STRUCTURAL CHECKS
# ═══════════════════════════════════════════════════════════════════

# Keyword -> area mapping for mismatch detection
AREA_KEYWORDS = {
    'PLUMBING': ['tap', 'pipe', 'drain', 'shower', 'basin', 'valve', 'geyser', 'water'],
    'DOORS': ['door', 'handle', 'lock', 'hinge', 'closer', 'stop', 'frame'],
    'WINDOWS': ['window', 'glass', 'burglar', 'seal'],
    'FLOOR': ['tile', 'grout', 'skirting', 'floor'],
    'WALLS': ['plaster', 'paint', 'wall', 'crack', 'damp'],
    'JOINERY': ['bic', 'cupboard', 'drawer', 'shelf', 'counter', 'desk'],
    'ELECTRICAL': ['switch', 'plug', 'light', 'isolator', 'db board'],
}


def _detect_area_from_description(desc):
    """Return set of area names suggested by keywords in the description."""
    desc_lower = desc.lower() if desc else ''
    suggested = set()
    for area, keywords in AREA_KEYWORDS.items():
        for kw in keywords:
            if kw in desc_lower:
                suggested.add(area)
                break
    return suggested


@data_quality_bp.route('/structural')
@require_admin
def structural():
    """Tab 2: Structural Checks - mismatches, duplicates, orphans, wash sync."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    # ── KPI Cards ──────────────────────────────────────────

    # 2A: Area mismatches - computed in Python after query
    mismatch_raw = query_db(
        "SELECT d.id AS defect_id, d.original_comment, "
        "  u.unit_number, at2.area_name, ct.category_name, "
        "  it.item_description "
        "FROM defect d "
        "JOIN unit u ON d.unit_id = u.id "
        "JOIN item_template it ON d.item_template_id = it.id "
        "JOIN category_template ct ON it.category_id = ct.id "
        "JOIN area_template at2 ON ct.area_id = at2.id "
        "WHERE d.status='open' AND d.tenant_id=? "
        "AND d.original_comment IS NOT NULL",
        (tenant_id,)
    )
    mismatches = []
    for r in mismatch_raw:
        row = dict(r)
        suggested = _detect_area_from_description(row['original_comment'])
        actual_cat = row['category_name'].upper() if row['category_name'] else ''
        # Flag if description suggests a DIFFERENT category and does NOT match actual
        if suggested and actual_cat not in suggested:
            row['suggested_categories'] = ', '.join(sorted(suggested))
            mismatches.append(row)

    # 2B: Duplicates
    dup_raw = query_db(
        "SELECT d.unit_id, u.unit_number, d.item_template_id, "
        "  it.item_description, ct.category_name, "
        "  COUNT(*) AS duplicate_count, "
        "  GROUP_CONCAT(d.id, '|') AS defect_ids, "
        "  GROUP_CONCAT(d.original_comment, '|') AS descriptions "
        "FROM defect d "
        "JOIN unit u ON d.unit_id = u.id "
        "JOIN item_template it ON d.item_template_id = it.id "
        "JOIN category_template ct ON it.category_id = ct.id "
        "WHERE d.status='open' AND d.tenant_id=? "
        "GROUP BY d.unit_id, d.item_template_id "
        "HAVING duplicate_count > 1 "
        "ORDER BY duplicate_count DESC",
        (tenant_id,)
    )
    duplicates = []
    for r in dup_raw:
        row = dict(r)
        row['defect_id_list'] = row['defect_ids'].split('|') if row['defect_ids'] else []
        row['description_list'] = row['descriptions'].split('|') if row['descriptions'] else []
        duplicates.append(row)

    # 2C: Orphan inspection items (NTS/NI with no defect)
    orphan_raw = query_db(
        "SELECT u.unit_number, it.item_description, ct.category_name, "
        "  ii.status AS item_status, ii.id AS item_id, ii.comment, "
        "  i.cycle_id "
        "FROM inspection_item ii "
        "JOIN inspection i ON ii.inspection_id = i.id "
        "JOIN unit u ON i.unit_id = u.id "
        "JOIN item_template it ON ii.item_template_id = it.id "
        "JOIN category_template ct ON it.category_id = ct.id "
        "LEFT JOIN defect d ON d.unit_id = u.id "
        "  AND d.item_template_id = ii.item_template_id "
        "  AND d.raised_cycle_id = i.cycle_id "
        "WHERE ii.status IN ('not_to_standard', 'not_installed') "
        "AND d.id IS NULL "
        "AND i.tenant_id=? "
        "AND i.cycle_id NOT LIKE 'test-%'",
        (tenant_id,)
    )
    orphans = [dict(r) for r in orphan_raw]

    # 2D: Wash mismatches (defect.original_comment != inspection_item.comment)
    wash_raw = query_db(
        "SELECT u.unit_number, it.item_description, "
        "  d.original_comment AS washed, "
        "  ii.comment AS raw, "
        "  d.id AS defect_id, ii.id AS item_id "
        "FROM defect d "
        "JOIN unit u ON d.unit_id = u.id "
        "JOIN item_template it ON d.item_template_id = it.id "
        "JOIN inspection i ON i.unit_id = d.unit_id AND i.cycle_id = d.raised_cycle_id "
        "JOIN inspection_item ii ON ii.inspection_id = i.id "
        "  AND ii.item_template_id = d.item_template_id "
        "WHERE d.tenant_id=? AND d.status='open' "
        "AND ii.comment IS NOT NULL AND ii.comment != '' "
        "AND ii.comment != d.original_comment",
        (tenant_id,)
    )
    wash_mismatches = [dict(r) for r in wash_raw]

    kpis = {
        'mismatches': len(mismatches),
        'duplicates': len(duplicates),
        'orphans': len(orphans),
        'wash_mismatches': len(wash_mismatches),
    }

    return render_template('data_quality/structural.html',
                           kpis=kpis,
                           mismatches=mismatches,
                           duplicates=duplicates,
                           orphans=orphans,
                           wash_mismatches=wash_mismatches)


@data_quality_bp.route('/reset-orphan', methods=['POST'])
@require_admin
def reset_orphan():
    """Reset an orphan inspection item back to OK status."""
    item_id = request.form.get('item_id', '').strip()
    if not item_id:
        return ('<tr class="bg-red-50"><td colspan="5" class="px-4 py-3 text-sm text-red-600">'
                'No item ID provided.</td></tr>')

    db = get_db()
    db.execute(
        "UPDATE inspection_item SET status='ok', comment=NULL WHERE id=?",
        (item_id,)
    )
    db.commit()

    return ('<tr class="bg-green-50"><td colspan="5" class="px-4 py-3 text-sm text-green-700">'
            '<strong>Fixed.</strong> Item reset to OK.</td></tr>')


@data_quality_bp.route('/delete-defect', methods=['POST'])
@require_admin
def delete_defect():
    """Delete a single defect record (for duplicate cleanup)."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    defect_id = request.form.get('defect_id', '').strip()
    if not defect_id:
        return ('<tr class="bg-red-50"><td colspan="5" class="px-4 py-3 text-sm text-red-600">'
                'No defect ID provided.</td></tr>')

    db = get_db()
    # Verify it exists and belongs to tenant
    row = db.execute(
        "SELECT id FROM defect WHERE id=? AND tenant_id=?",
        (defect_id, tenant_id)
    ).fetchone()
    if not row:
        return ('<tr class="bg-amber-50"><td colspan="5" class="px-4 py-3 text-sm text-amber-600">'
                'Defect not found.</td></tr>')

    db.execute("DELETE FROM defect WHERE id=?", (defect_id,))
    db.commit()

    return ('<tr class="bg-green-50"><td colspan="5" class="px-4 py-3 text-sm text-green-700">'
            '<strong>Deleted.</strong> Defect {} removed.</td></tr>').format(defect_id[:8])


@data_quality_bp.route('/sync-wash', methods=['POST'])
@require_admin
def sync_wash():
    """Sync a single inspection_item.comment to match defect.original_comment."""
    item_id = request.form.get('item_id', '').strip()
    washed = request.form.get('washed', '').strip()
    if not item_id or not washed:
        return ('<tr class="bg-red-50"><td colspan="5" class="px-4 py-3 text-sm text-red-600">'
                'Missing data.</td></tr>')

    db = get_db()
    db.execute(
        "UPDATE inspection_item SET comment=? WHERE id=?",
        (washed, item_id)
    )
    db.commit()

    return ('<tr class="bg-green-50"><td colspan="5" class="px-4 py-3 text-sm text-green-700">'
            '<strong>Synced.</strong> Inspection item updated to washed description.</td></tr>')


@data_quality_bp.route('/sync-wash-all', methods=['POST'])
@require_admin
def sync_wash_all():
    """Bulk sync all inspection_item.comment to match defect.original_comment."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    db = get_db()
    # Find all mismatches and fix them
    rows = db.execute(
        "SELECT ii.id AS item_id, d.original_comment AS washed "
        "FROM defect d "
        "JOIN inspection i ON i.unit_id = d.unit_id AND i.cycle_id = d.raised_cycle_id "
        "JOIN inspection_item ii ON ii.inspection_id = i.id "
        "  AND ii.item_template_id = d.item_template_id "
        "WHERE d.tenant_id=? AND d.status='open' "
        "AND ii.comment IS NOT NULL AND ii.comment != '' "
        "AND ii.comment != d.original_comment",
        (tenant_id,)
    ).fetchall()

    count = 0
    for r in rows:
        db.execute(
            "UPDATE inspection_item SET comment=? WHERE id=?",
            (r[1], r[0])
        )
        count += 1

    db.commit()

    return (
        '<div class="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-700">'
        '<strong>Bulk sync complete.</strong> {} inspection item{} updated to match '
        'washed defect descriptions.</div>'
    ).format(count, 's' if count != 1 else '')


# ===================================================================
# TAB 3: LIBRARY AUDIT
# ===================================================================

@data_quality_bp.route('/library')
@require_admin
def library():
    """Tab 3: Library Audit - overview, top entries, dead entries, merges, orphans."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    # -- KPI Cards --
    total = dict(query_db(
        "SELECT COUNT(*) AS cnt FROM defect_library WHERE tenant_id=?",
        (tenant_id,), one=True
    ))['cnt']

    active = dict(query_db(
        "SELECT COUNT(*) AS cnt FROM defect_library "
        "WHERE tenant_id=? AND usage_count > 0",
        (tenant_id,), one=True
    ))['cnt']

    dead = dict(query_db(
        "SELECT COUNT(*) AS cnt FROM defect_library "
        "WHERE tenant_id=? AND usage_count = 0",
        (tenant_id,), one=True
    ))['cnt']

    item_specific = dict(query_db(
        "SELECT COUNT(*) AS cnt FROM defect_library "
        "WHERE tenant_id=? AND item_template_id IS NOT NULL",
        (tenant_id,), one=True
    ))['cnt']

    category_only = dict(query_db(
        "SELECT COUNT(*) AS cnt FROM defect_library "
        "WHERE tenant_id=? AND item_template_id IS NULL",
        (tenant_id,), one=True
    ))['cnt']

    kpis = {
        'total': total,
        'active': active,
        'dead': dead,
        'item_specific': item_specific,
        'category_only': category_only,
    }

    # -- 3B: Top 20 by usage --
    top20_raw = query_db(
        "SELECT dl.description, dl.category_name, dl.usage_count, "
        "  dl.item_template_id, it.item_description "
        "FROM defect_library dl "
        "LEFT JOIN item_template it ON dl.item_template_id = it.id "
        "WHERE dl.tenant_id=? "
        "ORDER BY dl.usage_count DESC "
        "LIMIT 20",
        (tenant_id,)
    )
    top20 = [dict(r) for r in top20_raw]

    # -- 3C: Dead entries (zero usage) --
    dead_raw = query_db(
        "SELECT dl.id, dl.description, dl.category_name, "
        "  dl.item_template_id, it.item_description "
        "FROM defect_library dl "
        "LEFT JOIN item_template it ON dl.item_template_id = it.id "
        "WHERE dl.tenant_id=? AND dl.usage_count = 0 "
        "ORDER BY dl.category_name, dl.description",
        (tenant_id,)
    )
    dead_entries = [dict(r) for r in dead_raw]

    # -- 3D: Potential merges (similar library entries within same category) --
    lib_raw = query_db(
        "SELECT dl.id, dl.description, dl.category_name, dl.usage_count "
        "FROM defect_library dl "
        "WHERE dl.tenant_id=? AND dl.usage_count > 0 "
        "ORDER BY dl.category_name, dl.usage_count DESC",
        (tenant_id,)
    )
    lib_entries = [dict(r) for r in lib_raw]
    merge_pairs = _compute_library_merges(lib_entries)

    # -- 3E: Orphan library entries (template_id points to nothing) --
    orphan_raw = query_db(
        "SELECT dl.id, dl.description, dl.item_template_id, "
        "  dl.category_name, dl.usage_count "
        "FROM defect_library dl "
        "LEFT JOIN item_template it ON dl.item_template_id = it.id "
        "WHERE dl.tenant_id=? "
        "AND dl.item_template_id IS NOT NULL "
        "AND it.id IS NULL",
        (tenant_id,)
    )
    orphan_entries = [dict(r) for r in orphan_raw]

    return render_template('data_quality/library.html',
                           kpis=kpis,
                           top20=top20,
                           dead_entries=dead_entries,
                           merge_pairs=merge_pairs,
                           orphan_entries=orphan_entries)


def _compute_library_merges(entries):
    """
    Find pairs of library entries within the same category that are
    >0.8 similar. Returns list of dicts with both entries and score.
    """
    by_category = {}
    for e in entries:
        cat = e['category_name'] or 'UNKNOWN'
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(e)

    pairs = []
    seen = set()
    for cat, members in by_category.items():
        n = len(members)
        for i in range(n):
            for j in range(i + 1, n):
                a = members[i]
                b = members[j]
                key = (min(a['id'], b['id']), max(a['id'], b['id']))
                if key in seen:
                    continue
                score = SequenceMatcher(
                    None,
                    a['description'].lower().strip(),
                    b['description'].lower().strip()
                ).ratio()
                if score >= 0.8:
                    seen.add(key)
                    # Higher usage first
                    if a['usage_count'] >= b['usage_count']:
                        keep, remove = a, b
                    else:
                        keep, remove = b, a
                    pairs.append({
                        'category': cat,
                        'keep_id': keep['id'],
                        'keep_desc': keep['description'],
                        'keep_usage': keep['usage_count'],
                        'remove_id': remove['id'],
                        'remove_desc': remove['description'],
                        'remove_usage': remove['usage_count'],
                        'score': round(score * 100),
                    })

    pairs.sort(key=lambda x: x['keep_usage'] + x['remove_usage'], reverse=True)
    return pairs


@data_quality_bp.route('/delete-library-entry', methods=['POST'])
@require_admin
def delete_library_entry():
    """Delete a single library entry."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    entry_id = request.form.get('entry_id', '').strip()
    if not entry_id:
        return ('<tr class="bg-red-50"><td colspan="5" class="px-4 py-3 text-sm text-red-600">'
                'No entry ID provided.</td></tr>')

    db = get_db()
    row = db.execute(
        "SELECT id FROM defect_library WHERE id=? AND tenant_id=?",
        (entry_id, tenant_id)
    ).fetchone()
    if not row:
        return ('<tr class="bg-amber-50"><td colspan="5" class="px-4 py-3 text-sm text-amber-600">'
                'Entry not found.</td></tr>')

    db.execute("DELETE FROM defect_library WHERE id=?", (entry_id,))
    db.commit()

    return ('<tr class="bg-green-50"><td colspan="5" class="px-4 py-3 text-sm text-green-700">'
            '<strong>Deleted.</strong> Library entry removed.</td></tr>')


@data_quality_bp.route('/bulk-delete-dead', methods=['POST'])
@require_admin
def bulk_delete_dead():
    """Delete all library entries with zero usage."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    db = get_db()
    count_row = db.execute(
        "SELECT COUNT(*) FROM defect_library "
        "WHERE tenant_id=? AND usage_count = 0",
        (tenant_id,)
    ).fetchone()
    count = count_row[0] if count_row else 0

    db.execute(
        "DELETE FROM defect_library WHERE tenant_id=? AND usage_count = 0",
        (tenant_id,)
    )
    db.commit()

    return (
        '<div class="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-700">'
        '<strong>Bulk delete complete.</strong> {} dead library entr{} removed.</div>'
    ).format(count, 'ies' if count != 1 else 'y')


@data_quality_bp.route('/convert-to-category', methods=['POST'])
@require_admin
def convert_to_category():
    """Convert a library entry from item-specific to category-only."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    entry_id = request.form.get('entry_id', '').strip()
    if not entry_id:
        return ('<tr class="bg-red-50"><td colspan="4" class="px-4 py-3 text-sm text-red-600">'
                'No entry ID provided.</td></tr>')

    db = get_db()
    db.execute(
        "UPDATE defect_library SET item_template_id = NULL "
        "WHERE id=? AND tenant_id=?",
        (entry_id, tenant_id)
    )
    db.commit()

    return ('<tr class="bg-green-50"><td colspan="4" class="px-4 py-3 text-sm text-green-700">'
            '<strong>Converted.</strong> Entry is now category-only.</td></tr>')


@data_quality_bp.route('/merge-library-pair', methods=['POST'])
@require_admin
def merge_library_pair():
    """Merge two library entries: keep one, delete the other, update defects."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    keep_id = request.form.get('keep_id', '').strip()
    remove_id = request.form.get('remove_id', '').strip()
    keep_desc = request.form.get('keep_desc', '').strip()
    remove_desc = request.form.get('remove_desc', '').strip()

    if not keep_id or not remove_id:
        return ('<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-600">'
                'Missing IDs.</div>')

    db = get_db()

    # Update any defects using the removed description
    affected_row = db.execute(
        "SELECT COUNT(*) FROM defect "
        "WHERE original_comment=? AND status='open' AND tenant_id=?",
        (remove_desc, tenant_id)
    ).fetchone()
    affected = affected_row[0] if affected_row else 0

    if affected > 0:
        db.execute(
            "UPDATE defect SET original_comment=?, updated_at=CURRENT_TIMESTAMP "
            "WHERE original_comment=? AND status='open' AND tenant_id=?",
            (keep_desc, remove_desc, tenant_id)
        )

    # Transfer usage count and delete removed entry
    db.execute(
        "UPDATE defect_library SET usage_count = usage_count + "
        "(SELECT usage_count FROM defect_library WHERE id=?) "
        "WHERE id=?",
        (remove_id, keep_id)
    )
    db.execute("DELETE FROM defect_library WHERE id=?", (remove_id,))

    db.commit()

    return (
        '<div class="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-700">'
        '<strong>Merged.</strong> '
        '<span class="line-through text-gray-400">{}</span> '
        '&rarr; <strong>{}</strong>. '
        '{} defect{} updated. Library entry removed.</div>'
    ).format(remove_desc, keep_desc, affected, 's' if affected != 1 else '')