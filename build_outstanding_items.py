#!/usr/bin/env python3
"""
Outstanding Items List - first iteration (HTML view only).
For Ralph Rhoda / site teams - consolidated punch list of all open defects
+ outstanding latent, project-wide, grouped Block -> Floor -> Unit -> Area.

Adds:
  - _build_outstanding_items_data(tenant_id) in analytics.py
  - GET /analytics/outstanding-items route in analytics.py
  - new template app/templates/analytics/outstanding_items.html

No PDF route yet. No nav link yet (direct URL access first iteration).

Idempotent. Asserts. Atomic.
"""
from pathlib import Path

ANALYTICS = Path("app/routes/analytics.py")
TEMPLATE = Path("app/templates/analytics/outstanding_items.html")

assert ANALYTICS.exists(), f"Not found: {ANALYTICS}"

MARKER_HELPER = "def _build_outstanding_items_data("
MARKER_ROUTE = "def outstanding_items_view("


HELPER_AND_ROUTE = '''


# ============================================================================
# Outstanding Items List (Site Punch List for Ralph + site teams)
# ============================================================================

def _build_outstanding_items_data(tenant_id):
    """All open defects + outstanding latent, grouped Block -> Floor -> Unit -> Area.

    Live data (no snapshot freeze). For Ralph Rhoda's site teams to plan
    rectification sweeps. Latent notes are exploded into individual bullet
    items so each actionable line gets its own row.
    """
    import sqlite3, re
    from datetime import datetime, timezone, timedelta

    conn = sqlite3.connect('/var/data/inspections.db')
    conn.row_factory = sqlite3.Row

    now = datetime.now(timezone.utc)
    sast = now.astimezone(timezone(timedelta(hours=2)))
    snapshot_label = sast.strftime('%d %b %Y %H:%M SAST')

    try:
        defect_rows = conn.execute("""
            SELECT u.block, u.floor, u.unit_number,
                   at.area_name, at.area_order,
                   ct.category_name AS trade, ct.category_order,
                   it.item_description, it.item_order,
                   COALESCE(NULLIF(d.reviewed_comment,''), NULLIF(d.raw_comment,''), d.original_comment) AS description,
                   d.raised_cycle_number, d.created_at
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id AND it.tenant_id = d.tenant_id
            JOIN category_template ct ON it.category_id = ct.id AND ct.tenant_id = d.tenant_id
            JOIN area_template at ON ct.area_id = at.id AND at.tenant_id = d.tenant_id
            JOIN unit_real u ON d.unit_id = u.id AND u.tenant_id = d.tenant_id
            WHERE d.tenant_id = ? AND d.status = 'open'
            ORDER BY u.block, u.floor, CAST(u.unit_number AS INTEGER),
                     at.area_order, ct.category_order, it.item_order
        """, (tenant_id,)).fetchall()

        latent_rows = conn.execute("""
            SELECT u.block, u.floor, u.unit_number,
                   at.area_name, at.area_order,
                   lan.note_html, lan.cycle_number, lan.created_at
            FROM latent_area_note lan
            JOIN area_template at ON lan.area_template_id = at.id AND at.tenant_id = lan.tenant_id
            JOIN unit_real u ON lan.unit_id = u.id AND u.tenant_id = lan.tenant_id
            WHERE lan.tenant_id = ? AND lan.rectified_at IS NULL
            ORDER BY u.block, u.floor, CAST(u.unit_number AS INTEGER), at.area_order
        """, (tenant_id,)).fetchall()
    finally:
        conn.close()

    def _parse_created_at(s):
        if not s:
            return None
        s = s.replace('T', ' ').split('+')[0].split('.')[0]
        try:
            return datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        except Exception:
            return None

    units_dict = {}
    trade_counts = {}

    def _get_unit(block, floor, unit_number):
        key = (block, floor, unit_number)
        if key not in units_dict:
            units_dict[key] = {
                'block': block,
                'floor': floor,
                'floor_label': _FL_LABELS.get(floor, 'Floor {}'.format(floor)),
                'unit_number': unit_number,
                'open_count': 0,
                'latent_count': 0,
                'oldest_age_days': 0,
                '_areas': {},
            }
        return units_dict[key]

    def _get_area(unit, name, order):
        if name not in unit['_areas']:
            unit['_areas'][name] = {'name': name, 'area_order': order or 99, 'defects': []}
        return unit['_areas'][name]

    # Defects
    for r in defect_rows:
        u = _get_unit(r['block'], r['floor'], r['unit_number'])
        a = _get_area(u, r['area_name'], r['area_order'])
        ca = _parse_created_at(r['created_at'])
        age_days = (now - ca).days if ca else 0
        cyc = r['raised_cycle_number']
        a['defects'].append({
            'trade': r['trade'] or '',
            'description': (r['description'] or '').strip(),
            'cycle': 'C{}'.format(cyc) if cyc else '',
            'is_latent': False,
            'age_days': age_days,
        })
        u['open_count'] += 1
        if age_days > u['oldest_age_days']:
            u['oldest_age_days'] = age_days
        t = r['trade'] or 'OTHER'
        trade_counts[t] = trade_counts.get(t, 0) + 1

    # Latent (explode bullets)
    _BULLET_RE = re.compile(r'<li[^>]*>(.*?)</li>', re.DOTALL | re.IGNORECASE)
    _TAG_RE = re.compile(r'<[^>]+>')
    for r in latent_rows:
        u = _get_unit(r['block'], r['floor'], r['unit_number'])
        a = _get_area(u, r['area_name'], r['area_order'])
        html = r['note_html'] or ''
        bullets = _BULLET_RE.findall(html)
        if not bullets:
            txt = _TAG_RE.sub(' ', html).strip()
            if txt:
                bullets = [txt]
        ca = _parse_created_at(r['created_at'])
        age_days = (now - ca).days if ca else 0
        cyc = r['cycle_number']
        for b in bullets:
            txt = _TAG_RE.sub(' ', b).strip()
            txt = re.sub(r'\\s+', ' ', txt)
            if not txt:
                continue
            a['defects'].append({
                'trade': 'LATENT',
                'description': txt,
                'cycle': 'C{}'.format(cyc) if cyc else '',
                'is_latent': True,
                'age_days': age_days,
            })
            u['latent_count'] += 1
            if age_days > u['oldest_age_days']:
                u['oldest_age_days'] = age_days

    # Finalise: sort units, expand areas
    def _unit_key(k):
        try:
            return (k[0], k[1], int(k[2]))
        except (ValueError, TypeError):
            return (k[0], k[1], 0)

    units_list = []
    for key in sorted(units_dict.keys(), key=_unit_key):
        u = units_dict[key]
        u['areas'] = sorted(u['_areas'].values(), key=lambda x: x['area_order'])
        u['oldest_age_weeks'] = u['oldest_age_days'] // 7
        del u['_areas']
        units_list.append(u)

    by_trade = sorted(
        [{'name': t, 'count': c} for t, c in trade_counts.items()],
        key=lambda x: -x['count']
    )

    total_open = sum(u['open_count'] for u in units_list)
    total_latent = sum(u['latent_count'] for u in units_list)

    return {
        'snapshot_label': snapshot_label,
        'totals': {
            'open_defects': total_open,
            'latent_outstanding': total_latent,
            'units_affected': len(units_list),
            'by_trade': by_trade,
        },
        'units': units_list,
    }


@analytics_bp.route('/outstanding-items')
@require_team_lead
def outstanding_items_view():
    """Outstanding Items List - HTML view (Site Punch List)."""
    import datetime as _dt, base64 as _b64, os as _os
    from flask import current_app as _ca
    _tenant = session.get('tenant_id', 'MONOGRAPH')
    data = _build_outstanding_items_data(_tenant)
    data['is_pdf'] = False
    data['report_date'] = _dt.datetime.now().strftime('%d %B %Y')
    logo_path = _os.path.join(_ca.static_folder, 'monograph_logo.jpg')
    if _os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            data['logo_b64'] = _b64.b64encode(f.read()).decode()
    else:
        data['logo_b64'] = ''
    return render_template('analytics/outstanding_items.html', **data)
'''


TEMPLATE_CONTENT = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Outstanding Items List - Power Park Phase 3</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
@page { size: A4; margin: 16mm 12mm 16mm 12mm; }
* { box-sizing: border-box; }
body {
    font-family: 'DM Sans', system-ui, sans-serif;
    font-size: 9pt;
    color: #1A1A1A;
    margin: 0;
    line-height: 1.4;
    background: #FFFFFF;
}
.report-wrap { max-width: 210mm; margin: 0 auto; padding: 14mm 12mm; background: #FFFFFF; }
@media print { .report-wrap { padding: 0; max-width: none; } }
.report-header {
    display: flex; justify-content: space-between; align-items: flex-end;
    border-bottom: 2px solid #1A1A1A;
    padding-bottom: 8px; margin-bottom: 14px;
}
.report-header img { height: 32px; width: auto; }
.report-header .meta { text-align: right; font-size: 8pt; color: #6B6B6B; letter-spacing: 1.5px; text-transform: uppercase; line-height: 1.4; }
.report-header .meta .sub { color: #9A9A9A; }
.report-title {
    font-family: 'Cormorant Garamond', serif;
    font-weight: 500;
    font-size: 30pt;
    line-height: 1;
    margin: 0 0 4px 0;
    letter-spacing: -0.01em;
}
.report-subtitle { font-size: 11pt; color: #1A1A1A; margin: 0 0 2px 0; }
.report-meta { font-size: 9pt; color: #6B6B6B; font-style: italic; margin: 0 0 4px 0; }
.section-title {
    font-size: 8pt; font-weight: 700; color: #C8963E;
    letter-spacing: 1.5px; text-transform: uppercase;
    margin: 18px 0 8px 0;
}
.cover-stats {
    display: flex; gap: 24px;
    margin: 14px 0 0 0;
    padding: 14px 0;
    border-top: 1px solid #E8E6E1;
    border-bottom: 1px solid #E8E6E1;
}
.cover-stat { flex: 1; }
.cover-stat .num {
    font-family: 'Cormorant Garamond', serif;
    font-size: 28pt; font-weight: 600; line-height: 1;
    color: #C44D3F;
}
.cover-stat .num.latent { color: #C8963E; }
.cover-stat .num.units { color: #1A1A1A; }
.cover-stat .label {
    font-size: 8pt; color: #6B6B6B;
    text-transform: uppercase; letter-spacing: 1px;
    margin-top: 4px;
}
.trade-table { width: 100%; max-width: 380px; border-collapse: collapse; font-size: 9pt; }
.trade-table th {
    text-align: left; padding: 5px 8px; font-size: 7pt; font-weight: 600;
    color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase;
    border-bottom: 2px solid #E8E6E1;
}
.trade-table td { padding: 3px 8px; border-bottom: 1px solid #F0EEEA; }
.trade-table td.num { text-align: right; font-weight: 600; }

.unit-block { page-break-inside: avoid; break-inside: avoid; margin-bottom: 14px; }
.unit-header {
    background: #F5F3EE;
    padding: 5px 10px;
    border-left: 3px solid #C8963E;
    margin-bottom: 4px;
    display: flex; justify-content: space-between; align-items: baseline; gap: 8px;
}
.unit-id { font-size: 10pt; font-weight: 700; color: #1A1A1A; }
.unit-zone { font-size: 8pt; color: #6B6B6B; }
.unit-meta { font-size: 8pt; color: #6B6B6B; white-space: nowrap; }

.area-name {
    font-size: 8pt; font-weight: 600; color: #9A9A9A;
    letter-spacing: 1.2px; text-transform: uppercase;
    margin: 5px 0 1px 0;
}
.defect-row {
    display: flex; gap: 8px; font-size: 9pt;
    line-height: 1.45; padding: 1px 0 1px 14px;
    page-break-inside: avoid;
}
.defect-trade {
    flex: 0 0 92px;
    font-size: 8pt; font-weight: 600;
    color: #6B6B6B;
    text-transform: uppercase; letter-spacing: 0.5px;
    line-height: 1.5;
}
.defect-trade.latent { color: #C8963E; }
.defect-desc { flex: 1; color: #1A1A1A; }
.defect-cycle { flex: 0 0 28px; font-size: 8pt; color: #9A9A9A; text-align: right; line-height: 1.5; }

.empty-state {
    text-align: center; padding: 40px 0;
    color: #9A9A9A; font-style: italic; font-size: 11pt;
}
.footer {
    margin-top: 24px;
    padding-top: 8px;
    border-top: 1px solid #E8E6E1;
    font-size: 7pt; color: #9A9A9A; text-align: center;
    letter-spacing: 0.5px;
}
</style>
</head>
<body>
<div class="report-wrap">

<div class="report-header">
    <div>
        {% if logo_b64 %}<img src="data:image/jpeg;base64,{{ logo_b64 }}" alt="Monograph">{% endif %}
    </div>
    <div class="meta">
        {{ report_date }}<br>
        <span class="sub">Site Punch List</span>
    </div>
</div>

<h1 class="report-title">Outstanding Items List</h1>
<div class="report-subtitle">Power Park Student Housing &mdash; Phase 3</div>
<div class="report-meta">Live data &middot; {{ snapshot_label }} &middot; Scope: dwelling units only</div>

<div class="cover-stats">
    <div class="cover-stat">
        <div class="num">{{ totals.open_defects }}</div>
        <div class="label">Open Defects</div>
    </div>
    <div class="cover-stat">
        <div class="num latent">{{ totals.latent_outstanding }}</div>
        <div class="label">Latent Outstanding</div>
    </div>
    <div class="cover-stat">
        <div class="num units">{{ totals.units_affected }}</div>
        <div class="label">Units Affected</div>
    </div>
</div>

{% if totals.by_trade %}
<div class="section-title">By Trade</div>
<table class="trade-table">
    <thead>
        <tr>
            <th>Trade</th>
            <th style="text-align: right; width: 80px;">Open</th>
        </tr>
    </thead>
    <tbody>
        {% for t in totals.by_trade %}
        <tr>
            <td>{{ t.name }}</td>
            <td class="num">{{ t.count }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endif %}

<div style="page-break-before: always; padding-top: 4px;">
    <div class="section-title" style="margin-top: 0;">Open Items By Unit</div>

    {% if units %}
        {% for u in units %}
        <div class="unit-block">
            <div class="unit-header">
                <div>
                    <span class="unit-id">UNIT {{ u.unit_number }}</span>
                    <span class="unit-zone">&middot; {{ u.block }} / {{ u.floor_label }}</span>
                </div>
                <div class="unit-meta">
                    {{ u.open_count }} open{% if u.latent_count %} + {{ u.latent_count }} latent{% endif %}
                    {% if u.oldest_age_weeks %}&middot; oldest {{ u.oldest_age_weeks }} wk{% if u.oldest_age_weeks != 1 %}s{% endif %}{% endif %}
                </div>
            </div>
            {% for area in u.areas %}
            <div class="area-name">{{ area.name }}</div>
            {% for d in area.defects %}
            <div class="defect-row">
                <div class="defect-trade {% if d.is_latent %}latent{% endif %}">{{ d.trade if d.trade else '&mdash;' | safe }}</div>
                <div class="defect-desc">{{ d.description }}</div>
                <div class="defect-cycle">{{ d.cycle }}</div>
            </div>
            {% endfor %}
            {% endfor %}
        </div>
        {% endfor %}
    {% else %}
        <div class="empty-state">No open items. All units clear.</div>
    {% endif %}
</div>

<div class="footer">
    Confidential &mdash; Monograph Architects &middot; Power Park Student Housing Phase 3 &middot; {{ report_date }}
</div>

</div>
</body>
</html>
'''


def main():
    src = ANALYTICS.read_text()

    a_done = MARKER_HELPER in src and MARKER_ROUTE in src
    t_done = TEMPLATE.exists() and 'Outstanding Items List' in TEMPLATE.read_text()

    if a_done and t_done:
        print('[NO-OP] Already applied.')
        raise SystemExit(0)

    if not a_done:
        assert MARKER_HELPER not in src, 'Helper marker present but route absent - drift'
        assert MARKER_ROUTE not in src, 'Route marker present but helper absent - drift'
        assert 'def _build_brief_latent(' in src, 'Expected _build_brief_latent to exist'
        assert '_FL_LABELS' in src, 'Expected _FL_LABELS constant to exist'
        assert 'analytics_bp' in src, 'Expected analytics_bp blueprint to exist'

        new_src = src + HELPER_AND_ROUTE

        assert MARKER_HELPER in new_src
        assert MARKER_ROUTE in new_src
        assert "@analytics_bp.route('/outstanding-items')" in new_src
        assert new_src.count('def _build_outstanding_items_data') == 1
        assert new_src.count('def outstanding_items_view') == 1

        ANALYTICS.write_text(new_src)

    if not t_done:
        TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
        TEMPLATE.write_text(TEMPLATE_CONTENT)
        assert 'Outstanding Items List' in TEMPLATE.read_text()

    print('[OK] Outstanding Items List MVP built.')
    print(' analytics.py: helper + route appended')
    print(' template: app/templates/analytics/outstanding_items.html created')
    print()
    print('Access: https://inspections.archpractice.co.za/analytics/outstanding-items')
    print('Verify: git --no-pager diff --stat')


if __name__ == '__main__':
    main()
