filepath = 'app/templates/analytics/rectification.html'

with open(filepath, 'r') as f:
    content = f.read()

old = '''    {% set re_pct = (kpis.units_reinspected / kpis.total_inspected * 100)|round|int if kpis.total_inspected > 0 else 0 %}
    <div class="rounded-lg mb-4" style="border: 1px solid #e5e5e5; overflow: hidden;">
        <div style="padding: 1rem 1.25rem; background: #FAFAF8; border-bottom: 1px solid #e5e5e5;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <span style="font-size: 0.7rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #6B6B6B;">Re-inspection Progress</span>
                <span style="font-size: 0.8rem; font-weight: 600; color: #1A1A1A;">{{ kpis.units_reinspected }} of {{ kpis.total_inspected }} units ({{ re_pct }}%)</span>
            </div>
            <div style="height: 6px; background: #e5e5e5; border-radius: 3px; overflow: hidden;">
                <div style="width: {{ re_pct }}%; height: 100%; background: #3D6B8E; border-radius: 3px; min-width: 4px;"></div>
            </div>
        </div>
    </div>'''

new = '''    {# --- Project Pipeline (stacked bar by batch) --- #}
    {# TEMP: fabricated data for preview #}
    {% set pp_not_started = 100 %}
    {% set pp_awaiting = 75 %}
    {% set pp_in_rect = 16 %}
    {% set pp_in_rect_prev = 0 %}
    {% set pp_in_rect_delta = pp_in_rect - pp_in_rect_prev %}
    {% set pp_certified = 0 %}

    <div class="rect-panel mb-4" style="padding: 1.25rem;">
        <div style="font-size: 0.7rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #6B6B6B; margin-bottom: 0.75rem;">Project Pipeline</div>

        {# Metric cards #}
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; margin-bottom: 1rem;">
            <div style="background: #FAFAF8; border-radius: 6px; padding: 0.75rem; text-align: center; border-left: 3px solid #B4B2A9;">
                <div class="kpi-label" style="margin-top: 0; color: #B4B2A9;">Not started</div>
                <div class="kpi-value" style="font-size: 1.5rem; color: #1A1A1A;">{{ pp_not_started }}</div>
                <div class="kpi-sub">of 191 ({{ (pp_not_started / 191 * 100)|round|int }}%)</div>
            </div>
            <div style="background: #FAFAF8; border-radius: 6px; padding: 0.75rem; text-align: center; border-left: 3px solid #3D6B8E;">
                <div class="kpi-label" style="margin-top: 0; color: #3D6B8E;">Awaiting rectification</div>
                <div class="kpi-value" style="font-size: 1.5rem; color: #3D6B8E;">{{ pp_awaiting }}</div>
                <div class="kpi-sub">of {{ 191 - pp_not_started }} inspected</div>
            </div>
            <div style="background: #FAFAF8; border-radius: 6px; padding: 0.75rem; text-align: center; border-left: 3px solid #C8963E;">
                <div class="kpi-label" style="margin-top: 0; color: #C8963E;">In rectification</div>
                <div class="kpi-value" style="font-size: 1.5rem; color: #C8963E;">{{ pp_in_rect }}</div>
                <div class="kpi-sub">
                    {% if pp_in_rect_delta > 0 %}
                    <span style="color: #C44D3F; font-weight: 600;">&#9650; {{ pp_in_rect_delta }}</span> from last
                    {% elif pp_in_rect_delta < 0 %}
                    <span style="color: #4A7C59; font-weight: 600;">&#9660; {{ pp_in_rect_delta|abs }}</span> from last
                    {% else %}
                    <span style="color: #9A9A9A;">no change</span>
                    {% endif %}
                </div>
            </div>
            <div style="background: #FAFAF8; border-radius: 6px; padding: 0.75rem; text-align: center; border-left: 3px solid #4A7C59;">
                <div class="kpi-label" style="margin-top: 0; color: #4A7C59;">Certified</div>
                <div class="kpi-value" style="font-size: 1.5rem; color: #4A7C59;">{{ pp_certified }}</div>
                <div class="kpi-sub">of 191 ({{ (pp_certified / 191 * 100)|round|int }}%)</div>
            </div>
        </div>

        {# Legend #}
        <div style="display: flex; flex-wrap: wrap; gap: 1rem; font-size: 0.7rem; color: #6B6B6B; margin-bottom: 0.75rem;">
            <span><span class="severity-dot" style="background: #B4B2A9;"></span> Not inspected</span>
            <span><span class="severity-dot" style="background: #3D6B8E;"></span> Awaiting rectification</span>
            <span><span class="severity-dot" style="background: #C8963E;"></span> In rectification</span>
            <span><span class="severity-dot" style="background: #4A7C59;"></span> Certified</span>
        </div>

        {# Chart canvas #}
        <div style="position: relative; width: 100%; height: 340px;">
            <canvas id="pipelineChart"></canvas>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
    <script>
    (function() {
        var batches = [
            'Post\\nSR-009', 'Post\\nSR-010', 'Post\\nSR-011', 'Post\\nSR-012',
            'Post\\nSR-013', 'Post\\nSR-014', 'Post\\nSR-015'
        ];

        var certified =    [ 0,   0,  11,  24,  42,  68,  95];
        var inRect =       [ 0,  16,   5,  12,   8,   6,   4];
        var awaitingRect = [91,  75,  88,  78,  72,  60,  50];
        var notStarted =   [100,100,  87,  77,  69,  57,  42];

        var barLabelPlugin = {
            id: 'barLabelsInside',
            afterDraw: function(chart) {
                var ctx = chart.ctx;
                ctx.save();
                ctx.textAlign = 'center';
                var datasets = chart.data.datasets;
                for (var d = 0; d < datasets.length; d++) {
                    var meta = chart.getDatasetMeta(d);
                    for (var i = 0; i < meta.data.length; i++) {
                        var bar = meta.data[i];
                        var value = datasets[d].data[i];
                        if (value === 0) continue;
                        if (bar.height >= 18) {
                            ctx.font = '600 11px "DM Sans", system-ui, sans-serif';
                            ctx.fillStyle = '#FFFFFF';
                            ctx.fillText(value, bar.x, bar.y + bar.height / 2 + 4);
                        }
                    }
                }
                ctx.restore();
            }
        };

        new Chart(document.getElementById('pipelineChart'), {
            type: 'bar',
            data: {
                labels: batches,
                datasets: [
                    {
                        label: 'Certified',
                        data: certified,
                        backgroundColor: '#4A7C59',
                        borderRadius: {topLeft: 0, topRight: 0, bottomLeft: 3, bottomRight: 3},
                        order: 4
                    },
                    {
                        label: 'In rectification',
                        data: inRect,
                        backgroundColor: '#C8963E',
                        order: 3
                    },
                    {
                        label: 'Awaiting rectification',
                        data: awaitingRect,
                        backgroundColor: '#3D6B8E',
                        order: 2
                    },
                    {
                        label: 'Not inspected',
                        data: notStarted,
                        backgroundColor: '#B4B2A9',
                        borderRadius: {topLeft: 3, topRight: 3, bottomLeft: 0, bottomRight: 0},
                        order: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                return ctx.dataset.label + ': ' + ctx.raw + ' units';
                            },
                            footer: function(items) {
                                var total = items.reduce(function(s, i) { return s + i.raw; }, 0);
                                return 'Total: ' + total + ' / 191';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                        grid: { display: false },
                        border: { display: false },
                        ticks: {
                            font: { size: 11, family: '"DM Sans", system-ui, sans-serif' },
                            color: 'rgba(120,120,120,0.8)',
                            autoSkip: false,
                            maxRotation: 0
                        }
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        max: 191,
                        grid: { color: 'rgba(200,200,200,0.15)' },
                        border: { display: false },
                        ticks: {
                            font: { size: 11, family: '"DM Sans", system-ui, sans-serif' },
                            color: 'rgba(120,120,120,0.6)',
                            stepSize: 50
                        }
                    }
                }
            },
            plugins: [barLabelPlugin]
        });
    })();
    </script>'''

assert old in content, "MATCH FAILED"
content = content.replace(old, new, 1)

with open(filepath, 'w') as f:
    f.write(content)

print("OK - progress bar replaced with project pipeline chart")
