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