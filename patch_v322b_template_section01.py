"""
v322 Patch B - app/templates/analytics/site_meeting_brief.html
Page 1 - Section 01 redesign.

Two changes:
  1. Add new CSS rules for .kpi-grid, .kpi-tile, .handover-hero (and variants)
  2. Replace the prose .status-strip block with 4-tile KPI grid + auto-hiding hero panel

KPI tile order: INSPECTED | CERTIFIED | OPEN DEFECTS | LATENT DEFECTS
Accent stripes: gold / green / red / amber-brown
CERTIFIED tile has subtle green-tinted background.
Hero panel auto-hides when kpi.handover_ready == 0.
"""
import io

path = 'app/templates/analytics/site_meeting_brief.html'
with io.open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# --- Change 1: Insert CSS for KPI tiles + hero panel ---
# Anchor: insert immediately BEFORE existing /* Page footer scope text */ comment block

old_css_anchor = """/* Page footer scope text */
.section-overline {"""

new_css_block = """/* KPI tiles (Section 01) - v322 */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 16px;
}
.kpi-tile {
    background: #FFFFFF;
    border: 1px solid #E8E6E1;
    padding: 12px 14px 14px 14px;
    border-radius: 4px;
}
.kpi-tile-certified { background: #F4F8F2; }
.kpi-tile-label {
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #6B6B6B;
    margin-bottom: 6px;
}
.kpi-tile-value {
    font-size: 24px;
    font-weight: 700;
    color: #0A0A0A;
    line-height: 1.1;
    margin-bottom: 6px;
}
.kpi-tile-suffix {
    font-size: 13px;
    font-weight: 500;
    color: #6B6B6B;
}
.kpi-tile-meta {
    font-size: 9px;
    color: #6B6B6B;
    line-height: 1.4;
}

/* Handover-Ready hero panel (Section 01) - v322 */
.handover-hero {
    background: #F4F8F2;
    border: 1px solid #D4E2C9;
    border-left: 4px solid #4A7C59;
    border-radius: 4px;
    padding: 14px 16px;
    margin-bottom: 20px;
}
.handover-hero-title {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #4A7C59;
    margin-bottom: 6px;
}
.handover-hero-stat {
    margin-bottom: 10px;
    line-height: 1.3;
}
.handover-hero-num {
    font-size: 28px;
    font-weight: 700;
    color: #1A1A1A;
}
.handover-hero-suffix {
    font-size: 12px;
    color: #6B6B6B;
    margin-left: 6px;
}
.handover-hero-bar {
    display: flex;
    height: 22px;
    border-radius: 3px;
    overflow: hidden;
    border: 1px solid #E0E0E0;
}
.handover-hero-bar-open {
    background: #C44D3F;
    color: white;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 8px;
}
.handover-hero-bar-certified {
    background: #4A7C59;
    color: white;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 8px;
}

/* Page footer scope text */
.section-overline {"""

assert old_css_anchor in content, "PATCH B.1 MATCH FAILED: CSS anchor (section-overline)"
assert content.count(old_css_anchor) == 1, "PATCH B.1 NOT UNIQUE"
content = content.replace(old_css_anchor, new_css_block)

# --- Change 2: Replace Section 01 .status-strip with KPI tiles + hero panel ---

old_html = """        <div class="status-strip">
            <div class="line">
                <span class="num">{{ kpi.units_inspected }}</span> of <span class="num">{{ kpi.total_units }}</span> units inspected (<span class="num">{{ kpi.pct_complete }}%</span>){% if kpi.est_complete %} &mdash; first inspections expected to complete by <span class="num">{{ kpi.est_complete }}</span>{% endif %}
            </div>
            <div class="line">
                <span class="num">{{ '{:,}'.format(kpi.open_defects) }}</span> defects open across the site &mdash; averaging <span class="num">{{ kpi.avg_per_unit | round | int }}</span> per unit. The worst is Unit <span class="num">{{ kpi.worst_unit }}</span> with <span class="num">{{ kpi.worst_count }}</span> defects.
            </div>
            <div class="line" style="color: #9A9A9A;">
                Inspection scope: 454 items per unit &middot; project exclusion list of 55 items applied.
            </div>
            {% if latent_brief_summary and latent_brief_summary.total_identified > 0 %}
            <div class="line" style="color: #6B6B6B; font-size: 12px;">
                <span class="num">{{ latent_brief_summary.total_identified }}</span> latent defects identified during de-snag (<span class="num">{{ latent_brief_summary.affected_units_count }}</span> units affected, <span class="num">{{ latent_brief_summary.rectified_to_date_count }}</span> rectified to date).
            </div>
            {% endif %}
        </div>"""

new_html = """        <!-- v322: KPI tiles -->
        <div class="kpi-grid">
            <div class="kpi-tile" style="border-bottom: 4px solid #C8963E;">
                <div class="kpi-tile-label">Inspected</div>
                <div class="kpi-tile-value">{{ kpi.units_inspected }}<span class="kpi-tile-suffix"> of {{ kpi.total_units }}</span></div>
                <div class="kpi-tile-meta">{{ kpi.pct_complete }}% complete{% if kpi.est_complete %} &middot; est. {{ kpi.est_complete }}{% endif %}</div>
            </div>
            <div class="kpi-tile kpi-tile-certified" style="border-bottom: 4px solid #4A7C59;">
                <div class="kpi-tile-label">Certified</div>
                <div class="kpi-tile-value">{{ kpi.handover_ready }}</div>
                <div class="kpi-tile-meta">units with all defects cleared</div>
            </div>
            <div class="kpi-tile" style="border-bottom: 4px solid #C44D3F;">
                <div class="kpi-tile-label">Open Defects</div>
                <div class="kpi-tile-value">{{ '{:,}'.format(kpi.open_defects) }}</div>
                <div class="kpi-tile-meta">avg {{ kpi.avg_per_unit | round | int }} per unit &middot; worst Unit {{ kpi.worst_unit }} ({{ kpi.worst_count }})</div>
            </div>
            <div class="kpi-tile" style="border-bottom: 4px solid #A37116;">
                <div class="kpi-tile-label">Latent Defects</div>
                <div class="kpi-tile-value">{% if latent_brief_summary %}{{ latent_brief_summary.total_identified }}{% else %}0{% endif %}</div>
                <div class="kpi-tile-meta">{% if latent_brief_summary %}{{ latent_brief_summary.affected_units_count }} units &middot; {{ latent_brief_summary.rectified_to_date_count }} rectified{% else %}none identified{% endif %}</div>
            </div>
        </div>

        <!-- v322: Handover-Ready hero panel (auto-hide when 0) -->
        {% if kpi.handover_ready and kpi.handover_ready > 0 %}
        {% set hr_open = kpi.units_inspected - kpi.handover_ready %}
        {% set hr_pct = (kpi.handover_ready / kpi.units_inspected * 100)|round(1) if kpi.units_inspected > 0 else 0 %}
        <div class="handover-hero">
            <div class="handover-hero-title">Handover-Ready</div>
            <div class="handover-hero-stat">
                <span class="handover-hero-num">{{ kpi.handover_ready }}</span><span class="handover-hero-suffix">of {{ kpi.units_inspected }} inspected units have zero open defects</span>
            </div>
            <div class="handover-hero-bar">
                {% if hr_open > 0 %}
                <div class="handover-hero-bar-open" style="width: {{ 100 - hr_pct }}%;">{{ hr_open }} OPEN</div>
                {% endif %}
                {% if kpi.handover_ready > 0 %}
                <div class="handover-hero-bar-certified" style="width: {{ hr_pct }}%;">{{ kpi.handover_ready }} CERTIFIED</div>
                {% endif %}
            </div>
        </div>
        {% endif %}"""

assert old_html in content, "PATCH B.2 MATCH FAILED: status-strip block"
assert content.count(old_html) == 1, "PATCH B.2 NOT UNIQUE"
content = content.replace(old_html, new_html)

with io.open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('PATCH v322b APPLIED: site_meeting_brief.html - Section 01 KPI tiles + hero panel')
