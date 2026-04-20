// Audit Chart Morph — renders Zone-Adjusted Ranking chart bars
// in response to scrubber:change events from audit_scrubber.js.
// Reads the same #scrubber-data JSON blob. Idempotent re-render
// on every event; CSS transitions on width/opacity handle the animation.
(function () {
    'use strict';

    var dataEl = document.getElementById('scrubber-data');
    if (!dataEl) return;

    var payload;
    try {
        payload = JSON.parse(dataEl.textContent);
    } catch (e) {
        return;
    }

    var batchesData = payload.batches_data || {};
    var body = document.getElementById('zone-chart-body');
    var titleEl = document.getElementById('zone-chart-title');
    var subtitleEl = document.getElementById('zone-chart-subtitle');
    var calloutEl = document.getElementById('zone-chart-callout');
    if (!body) return;

    // Axis labels live in a sibling of the bars - server renders them once,
    // they are valid for every view so we don't touch them.

    function barRowHTML(insp) {
        var score = insp.zone_score;
        var absScore = Math.abs(score);
        var positive = score >= 0;
        var fillPct = Math.min(absScore * 0.4, 48);
        var showLabelInside = absScore > 5;
        var signedScore = (score > 0 ? '+' : '') + score + '%';
        var colour = insp.colour;

        var fillStyle, labelInside, labelOutside;
        if (positive) {
            fillStyle = 'left: 50%; top: 3px; height: 20px; width: ' + fillPct + '%; ' +
                        'background: ' + colour + '; border-radius: 0 4px 4px 0; ' +
                        'display: flex; align-items: center; justify-content: flex-end; padding-right: 4px;';
            labelInside = showLabelInside ? '<span style="font-size: 0.68rem; font-weight: 700; color: white;">' + signedScore + '</span>' : '';
            labelOutside = !showLabelInside
                ? '<div style="position: absolute; left: calc(50% + ' + fillPct + '% + 4px); top: 3px; height: 20px; display: flex; align-items: center; z-index: 3;">' +
                  '<span style="font-size: 0.7rem; font-weight: 700; color: ' + colour + ';">' + signedScore + '</span></div>'
                : '';
        } else {
            fillStyle = 'right: 50%; top: 3px; height: 20px; width: ' + fillPct + '%; ' +
                        'background: ' + colour + '; border-radius: 4px 0 0 4px; ' +
                        'display: flex; align-items: center; padding-left: 4px;';
            labelInside = showLabelInside ? '<span style="font-size: 0.68rem; font-weight: 700; color: white;">' + signedScore + '</span>' : '';
            labelOutside = !showLabelInside
                ? '<div style="position: absolute; right: calc(50% + ' + fillPct + '% + 4px); top: 3px; height: 20px; display: flex; align-items: center; z-index: 3;">' +
                  '<span style="font-size: 0.7rem; font-weight: 700; color: ' + colour + ';">' + signedScore + '</span></div>'
                : '';
        }

        return (
            '<div class="scrubber-bar-row" data-inspector="' + insp.inspector_id + '" data-score="' + score + '" data-units="' + insp.units + '" ' +
            'style="display: flex; align-items: center; margin-bottom: 0.5rem; padding: 2px 0; border-radius: 4px; transition: opacity 300ms ease;">' +
                '<div class="scrubber-bar-name" style="width: 130px; font-size: 0.78rem; font-weight: 600; color: #1A1A1A; text-align: right; padding-right: 0.5rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">' + insp.name + '</div>' +
                '<div style="flex: 1; position: relative; height: 26px; background: #e9e7e2; border-radius: 4px; overflow: visible;">' +
                    '<div style="position: absolute; left: 50%; top: 0; width: 1px; height: 26px; background: #6B6B6B; z-index: 2;"></div>' +
                    '<div style="position: absolute; transition: width 400ms cubic-bezier(0.4, 0, 0.2, 1), background 300ms ease; ' + fillStyle + ' z-index: 1;">' + labelInside + '</div>' +
                    labelOutside +
                '</div>' +
                '<div style="width: 70px; text-align: right; padding-left: 0.5rem;">' +
                    '<span style="font-size: 0.82rem; font-weight: 700; color: #1A1A1A;">' + insp.units + '</span>' +
                    '<span style="font-size: 0.7rem; color: #6B6B6B;"> units</span>' +
                '</div>' +
            '</div>'
        );
    }

    function axisHTML() {
        return (
            '<div style="display: flex; font-size: 0.65rem; color: #9A9A9A; margin-top: 0.3rem;">' +
                '<div style="width: 130px;"></div>' +
                '<div style="flex: 1; display: flex; justify-content: space-between; padding: 0 2px;">' +
                    '<span>&larr; fewer defects</span>' +
                    '<span>zone avg</span>' +
                    '<span>more defects &rarr;</span>' +
                '</div>' +
                '<div style="width: 70px;"></div>' +
            '</div>'
        );
    }

    function emptyStateHTML(batch) {
        return (
            '<div style="text-align: center; color: #9A9A9A; font-size: 0.82rem; padding: 2rem 0;">' +
                'No inspectors recorded for ' + (batch.short || batch.label) +
            '</div>'
        );
    }

    function render(batchKey) {
        var batch = batchesData[batchKey];
        if (!batch) return;

        // Swap title + subtitle + callout
        if (titleEl) titleEl.textContent = batch.title || 'Zone-Adjusted Ranking';
        if (subtitleEl) subtitleEl.textContent = batch.subtitle || '';
        if (calloutEl && batch.callout_html) {
            calloutEl.innerHTML = batch.callout_html;
            calloutEl.style.display = (batch.inspectors && batch.inspectors.length >= 1) ? '' : 'none';
        } else if (calloutEl) {
            calloutEl.style.display = 'none';
        }

        // Swap bars
        var inspectors = batch.inspectors || [];
        if (inspectors.length === 0) {
            body.innerHTML = emptyStateHTML(batch);
            return;
        }

        var html = inspectors.map(barRowHTML).join('') + axisHTML();
        body.innerHTML = html;
    }

    // Listen for scrubber changes. The scrubber fires this on initial load too
    // (with the URL-determined batch), so we don't need a separate init step.
    document.addEventListener('scrubber:change', function (e) {
        var key = e.detail && e.detail.key;
        if (key) render(key);
    });
})();
