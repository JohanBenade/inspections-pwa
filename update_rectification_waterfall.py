"""
Replace the three KPI cards and old legend in rectification.html
with waterfall chart + metric cards + closing balance colour key.
Numbers are fabricated for visual prototype (except Opening = 396 real data).
"""
import os

filepath = os.path.expanduser('~/Documents/GitHub/inspections-pwa/app/templates/analytics/rectification.html')

with open(filepath, 'r') as f:
    content = f.read()

old = '''        <div style="display: flex; padding: 0;">
            <div style="flex: 1; padding: 1rem 1.25rem; border-right: 1px solid #e5e5e5; border-left: 3px solid {% if kpis.net_improvement > 0 %}#4A7C59{% elif kpis.net_improvement < 0 %}#C44D3F{% else %}#6B6B6B{% endif %};">
                <div class="kpi-value" style="color: {% if kpis.net_improvement > 0 %}#4A7C59{% elif kpis.net_improvement < 0 %}#C44D3F{% else %}#6B6B6B{% endif %};">{{ '+' if kpis.net_improvement > 0 }}{{ kpis.net_improvement }}</div>
                <div class="kpi-label">Net Improvement</div>
                <div class="kpi-sub">{{ kpis.c1_cleared }} cleared &minus; {{ kpis.new_in_c2 }} new</div>
            </div>
            <div style="flex: 1; padding: 1rem 1.25rem; border-right: 1px solid #e5e5e5; border-left: 3px solid #4A7C59;">
                <div class="kpi-value" style="color: #4A7C59;">{{ kpis.c1_cleared }}</div>
                <div class="kpi-label">Rectified</div>
                <div class="kpi-sub">of {{ kpis.c1_reviewed }} flagged in C1</div>
            </div>
            <div style="flex: 1; padding: 1rem 1.25rem; border-left: 3px solid {% if kpis.new_in_c2 > 0 %}#D4730A{% else %}#4A7C59{% endif %};">
                <div class="kpi-value" style="color: {% if kpis.new_in_c2 > 0 %}#D4730A{% else %}#4A7C59{% endif %};">{{ kpis.new_in_c2 }}</div>
                <div class="kpi-label">New Defects</div>
                <div class="kpi-sub">found in re-inspection</div>
            </div>
        </div>
    </div>

    <div style="display: flex; flex-wrap: wrap; gap: 1.5rem; font-size: 0.7rem; color: #6B6B6B; margin-bottom: 1.5rem;">
        <span><span class="severity-dot" style="background: #4A7C59;"></span> Cleared (fixed)</span>
        <span><span class="severity-dot" style="background: #C44D3F;"></span> Still Open (unfixed)</span>
        <span><span class="severity-dot" style="background: #D4730A;"></span> New in C2</span>
    </div>'''

new = '''    </div>

    {# --- Defect Waterfall Chart --- #}
    {% set wf_opening = 396 %}
    {% set wf_rectified = 277 %}
    {% set wf_new = 23 %}
    {% set wf_closing = wf_opening - wf_rectified + wf_new %}
    {% set wf_remaining_pct = (wf_closing / wf_opening * 100)|round|int if wf_opening > 0 else 0 %}
    {% set wf_clearance_pct = (wf_rectified / wf_opening * 100)|round|int if wf_opening > 0 else 0 %}
    {% set wf_regression_pct = (wf_new / wf_opening * 100)|round|int if wf_opening > 0 else 0 %}
    {% if wf_remaining_pct <= 25 %}
        {% set wf_closing_colour = '#4A7C59' %}
    {% elif wf_remaining_pct <= 50 %}
        {% set wf_closing_colour = '#C8963E' %}
    {% else %}
        {% set wf_closing_colour = '#C44D3F' %}
    {% endif %}

    <div class="rect-panel mb-4" style="padding: 1.25rem;">
        <div style="font-size: 0.7rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #6B6B6B; margin-bottom: 0.75rem;">Defect Waterfall</div>

        {# Legend #}
        <div style="display: flex; flex-wrap: wrap; gap: 1rem; font-size: 0.7rem; color: #6B6B6B; margin-bottom: 0.75rem;">
            <span><span class="severity-dot" style="background: #6B6B6B;"></span> Opening balance</span>
            <span><span class="severity-dot" style="background: #4A7C59;"></span> Rectified</span>
            <span><span class="severity-dot" style="background: #D4730A;"></span> New defects</span>
            <span><span class="severity-dot" style="background: #C8963E;"></span> Closing balance</span>
        </div>

        {# Chart canvas #}
        <div style="position: relative; width: 100%; height: 320px;">
            <canvas id="waterfallChart"></canvas>
        </div>

        {# Metric cards #}
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; margin-top: 1rem;">
            <div style="background: #FAFAF8; border-radius: 6px; padding: 0.75rem; text-align: center; border-left: 3px solid #6B6B6B;">
                <div class="kpi-label" style="margin-top: 0;">Opening</div>
                <div class="kpi-value" style="font-size: 1.5rem; color: #1A1A1A;">{{ wf_opening }}</div>
                <div class="kpi-sub">C1 defects on 16 units</div>
            </div>
            <div style="background: #FAFAF8; border-radius: 6px; padding: 0.75rem; text-align: center; border-left: 3px solid #4A7C59;">
                <div class="kpi-label" style="margin-top: 0; color: #4A7C59;">Rectified</div>
                <div class="kpi-value" style="font-size: 1.5rem; color: #4A7C59;">&minus;{{ wf_rectified }}</div>
                <div class="kpi-sub">{{ wf_clearance_pct }}% clearance rate</div>
            </div>
            <div style="background: #FAFAF8; border-radius: 6px; padding: 0.75rem; text-align: center; border-left: 3px solid #D4730A;">
                <div class="kpi-label" style="margin-top: 0; color: #D4730A;">New in C2+</div>
                <div class="kpi-value" style="font-size: 1.5rem; color: #D4730A;">+{{ wf_new }}</div>
                <div class="kpi-sub">{{ wf_regression_pct }}% regression rate</div>
            </div>
            <div style="background: #FAFAF8; border-radius: 6px; padding: 0.75rem; text-align: center; border-left: 3px solid {{ wf_closing_colour }};">
                <div class="kpi-label" style="margin-top: 0; color: {{ wf_closing_colour }};">Closing balance</div>
                <div class="kpi-value" style="font-size: 1.5rem; color: {{ wf_closing_colour }};">{{ wf_closing }}</div>
                <div class="kpi-sub">{{ wf_remaining_pct }}% remaining</div>
            </div>
        </div>

        {# Closing balance colour key #}
        <div style="display: flex; flex-wrap: wrap; gap: 1rem; font-size: 0.65rem; color: #9A9A9A; margin-top: 0.75rem; justify-content: flex-end;">
            <span>Closing balance:</span>
            <span><span class="severity-dot" style="background: #4A7C59;"></span> &le;25% remaining</span>
            <span><span class="severity-dot" style="background: #C8963E;"></span> 26&ndash;50% remaining</span>
            <span><span class="severity-dot" style="background: #C44D3F;"></span> &gt;50% remaining</span>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
    <script>
    (function() {
        var opening = {{ wf_opening }};
        var rectified = {{ wf_rectified }};
        var newDef = {{ wf_new }};
        var closing = opening - rectified + newDef;
        var afterRect = opening - rectified;
        var closingColour = '{{ wf_closing_colour }}';

        var connectorPlugin = {
            id: 'waterfallConnectors',
            afterDraw: function(chart) {
                var ctx = chart.ctx;
                var meta0 = chart.getDatasetMeta(0);
                var meta1 = chart.getDatasetMeta(1);
                ctx.save();
                ctx.setLineDash([4, 3]);
                ctx.strokeStyle = 'rgba(120,120,120,0.35)';
                ctx.lineWidth = 1;
                var b0 = meta1.data[0]; var b1 = meta1.data[1];
                ctx.beginPath();
                ctx.moveTo(b0.x + b0.width / 2 + 2, b0.y);
                ctx.lineTo(b1.x - b1.width / 2 - 2, b1.y);
                ctx.stroke();
                var b2 = meta1.data[2];
                var rectBottom = b1.y + b1.height;
                ctx.beginPath();
                ctx.moveTo(b1.x + b1.width / 2 + 2, rectBottom);
                ctx.lineTo(b2.x - b2.width / 2 - 2, meta0.data[2].y + meta1.data[2].height);
                ctx.stroke();
                var b3 = meta1.data[3];
                ctx.beginPath();
                ctx.moveTo(b2.x + b2.width / 2 + 2, meta0.data[2].y);
                ctx.lineTo(b3.x - b3.width / 2 - 2, b3.y);
                ctx.stroke();
                ctx.restore();
            }
        };

        var labelPlugin = {
            id: 'waterfallLabels',
            afterDraw: function(chart) {
                var ctx = chart.ctx;
                var meta1 = chart.getDatasetMeta(1);
                var labels = [
                    { text: opening.toString(), idx: 0 },
                    { text: '-' + rectified, idx: 1 },
                    { text: '+' + newDef, idx: 2 },
                    { text: closing.toString(), idx: 3 }
                ];
                var colors = ['#6B6B6B', '#4A7C59', '#D4730A', closingColour];
                ctx.save();
                ctx.textAlign = 'center';
                ctx.font = '600 13px "DM Sans", system-ui, sans-serif';
                for (var i = 0; i < labels.length; i++) {
                    var bar = meta1.data[labels[i].idx];
                    ctx.fillStyle = colors[i];
                    ctx.fillText(labels[i].text, bar.x, bar.y - 8);
                }
                ctx.restore();
            }
        };

        new Chart(document.getElementById('waterfallChart'), {
            type: 'bar',
            data: {
                labels: ['Opening\nbalance', 'Rectified', 'New\ndefects', 'Closing\nbalance'],
                datasets: [
                    {
                        label: 'Base',
                        data: [0, afterRect, afterRect, 0],
                        backgroundColor: 'transparent',
                        borderWidth: 0,
                        barPercentage: 0.55,
                        categoryPercentage: 0.7
                    },
                    {
                        label: 'Value',
                        data: [opening, rectified, newDef, closing],
                        backgroundColor: ['#6B6B6B', '#4A7C59', '#D4730A', closingColour],
                        borderWidth: 0,
                        borderRadius: 3,
                        barPercentage: 0.55,
                        categoryPercentage: 0.7
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                    x: {
                        stacked: true,
                        grid: { display: false },
                        border: { display: false },
                        ticks: {
                            font: { size: 12, family: '"DM Sans", system-ui, sans-serif' },
                            color: 'rgba(120,120,120,0.8)',
                            autoSkip: false,
                            maxRotation: 0
                        }
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        max: Math.ceil(opening * 1.15 / 50) * 50,
                        grid: { color: 'rgba(200,200,200,0.2)', drawBorder: false },
                        border: { display: false },
                        ticks: {
                            font: { size: 11, family: '"DM Sans", system-ui, sans-serif' },
                            color: 'rgba(120,120,120,0.6)',
                            stepSize: 100
                        }
                    }
                }
            },
            plugins: [connectorPlugin, labelPlugin]
        });
    })();
    </script>'''

assert old in content, "MATCH FAILED - old text not found in rectification.html"

content = content.replace(old, new)

with open(filepath, 'w') as f:
    f.write(content)

print("OK - rectification.html updated with waterfall chart")
