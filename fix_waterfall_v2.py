filepath = 'app/templates/analytics/rectification.html'

with open(filepath, 'r') as f:
    content = f.read()

# Fix 1: Generic sub-text for opening balance
old1 = '<div class="kpi-sub">C1 defects on 16 units</div>'
new1 = '<div class="kpi-sub">across {{ kpis.units_reinspected }} re-inspected units</div>'

assert old1 in content, "MATCH FAILED on sub-text"
content = content.replace(old1, new1, 1)

# Fix 2: Rewrite connector plugin for correct bar-to-bar alignment
old2 = '''        var connectorPlugin = {
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
        };'''

new2 = '''        var connectorPlugin = {
            id: 'waterfallConnectors',
            afterDraw: function(chart) {
                var ctx = chart.ctx;
                var yScale = chart.scales.y;
                var meta1 = chart.getDatasetMeta(1);
                ctx.save();
                ctx.setLineDash([4, 3]);
                ctx.strokeStyle = 'rgba(120,120,120,0.35)';
                ctx.lineWidth = 1;
                var b0 = meta1.data[0];
                var b1 = meta1.data[1];
                var b2 = meta1.data[2];
                var b3 = meta1.data[3];
                /* Opening top (396) -> Rectified top (396): the level before drop */
                var yOpening = yScale.getPixelForValue(opening);
                ctx.beginPath();
                ctx.moveTo(b0.x + b0.width / 2 + 4, yOpening);
                ctx.lineTo(b1.x - b1.width / 2 - 4, yOpening);
                ctx.stroke();
                /* Rectified bottom (119) -> New bottom (119): the level after drop */
                var yAfterRect = yScale.getPixelForValue(afterRect);
                ctx.beginPath();
                ctx.moveTo(b1.x + b1.width / 2 + 4, yAfterRect);
                ctx.lineTo(b2.x - b2.width / 2 - 4, yAfterRect);
                ctx.stroke();
                /* New top (142) -> Closing top (142): the level after rise */
                var yClosing = yScale.getPixelForValue(closing);
                ctx.beginPath();
                ctx.moveTo(b2.x + b2.width / 2 + 4, yClosing);
                ctx.lineTo(b3.x - b3.width / 2 - 4, yClosing);
                ctx.stroke();
                ctx.restore();
            }
        };'''

assert old2 in content, "MATCH FAILED on connector plugin"
content = content.replace(old2, new2, 1)

with open(filepath, 'w') as f:
    f.write(content)

print("OK - fixed sub-text + connector alignment")
