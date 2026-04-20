// Audit Scrubber — batch filter for Zone-Adjusted Ranking chart.
// Commit 3: drag + snap + click + keyboard + URL sync.
// Commit 4 (separate): listens for scrubber:change to morph the chart.
(function () {
    'use strict';

    var dataEl = document.getElementById('scrubber-data');
    if (!dataEl) return;

    var payload;
    try {
        payload = JSON.parse(dataEl.textContent);
    } catch (e) {
        console.warn('Scrubber: failed to parse data blob', e);
        return;
    }

    var batches = payload.batches_list || [];
    if (batches.length < 2) return; // need "all" + at least one batch

    var trackWrap = document.getElementById('scrubber-track-wrap');
    var trackFill = document.getElementById('scrubber-track-fill');
    var thumb = document.getElementById('scrubber-thumb');
    var tooltip = document.getElementById('scrubber-tooltip');
    if (!trackWrap || !trackFill || !thumb || !tooltip) return;

    // --- Position helpers ---
    // Each node sits at an evenly-spaced position along the track.
    // Position in percent: i / (n - 1) * 100.
    var nCount = batches.length;
    function pctFor(index) {
        if (nCount <= 1) return 0;
        return (index / (nCount - 1)) * 100;
    }

    // --- Render nodes + labels ---
    function renderNodes() {
        batches.forEach(function (b, i) {
            var pct = pctFor(i);

            var node = document.createElement('div');
            node.className = 'scrubber-node ' + (b.key === 'all' ? 'all' : b.status || 'complete');
            node.style.left = pct + '%';
            node.setAttribute('data-index', i);
            node.setAttribute('data-key', b.key);
            node.setAttribute('title', b.key === 'all' ? 'All time (cumulative)' : b.label + ' — ' + b.unit_count + ' units');
            trackWrap.appendChild(node);

            var label = document.createElement('div');
            label.className = 'scrubber-label' + (b.key === 'all' ? ' all' : '');
            label.style.left = pct + '%';
            label.textContent = b.short || b.label;
            trackWrap.appendChild(label);
        });
    }
    renderNodes();

    // --- State ---
    var currentIndex = 0;

    function setIndex(i, opts) {
        opts = opts || {};
        if (i < 0) i = 0;
        if (i >= nCount) i = nCount - 1;
        currentIndex = i;

        var pct = pctFor(i);
        thumb.style.left = pct + '%';
        trackFill.style.width = pct + '%';

        var b = batches[i];
        if (b.key === 'all') {
            thumb.classList.add('all');
        } else {
            thumb.classList.remove('all');
        }

        // Tooltip content
        if (b.key === 'all') {
            tooltip.textContent = 'All time';
        } else {
            tooltip.textContent = b.short + (b.date ? ' · ' + b.date : '') + ' · ' + b.unit_count + ' units';
        }

        // URL sync (skip on initial load to avoid pushing a spurious entry)
        if (!opts.skipUrl) {
            try {
                var url = new URL(window.location.href);
                if (b.key === 'all') {
                    url.searchParams.delete('batch');
                } else {
                    url.searchParams.set('batch', b.key);
                }
                window.history.replaceState({}, '', url.toString());
            } catch (e) {
                // older browsers
            }
        }

        // Emit for Commit 4
        var ev;
        try {
            ev = new CustomEvent('scrubber:change', { detail: { key: b.key, batch: b, index: i } });
        } catch (e) {
            ev = document.createEvent('CustomEvent');
            ev.initCustomEvent('scrubber:change', false, false, { key: b.key, batch: b, index: i });
        }
        document.dispatchEvent(ev);
    }

    // --- Initial position from URL ---
    function initialIndex() {
        try {
            var url = new URL(window.location.href);
            var wanted = url.searchParams.get('batch');
            if (!wanted) return 0;
            for (var i = 0; i < batches.length; i++) {
                if (batches[i].key === wanted) return i;
            }
        } catch (e) {}
        return 0;
    }
    setIndex(initialIndex(), { skipUrl: true });

    // --- Click a node ---
    trackWrap.addEventListener('click', function (e) {
        var node = e.target.closest('.scrubber-node');
        if (!node) return;
        var idx = parseInt(node.getAttribute('data-index'), 10);
        if (!isNaN(idx)) setIndex(idx);
    });

    // --- Drag the thumb ---
    var dragging = false;

    function pctFromEvent(evt) {
        var rect = trackWrap.getBoundingClientRect();
        var clientX;
        if (evt.touches && evt.touches[0]) clientX = evt.touches[0].clientX;
        else clientX = evt.clientX;
        if (typeof clientX !== 'number') return 0;
        var pct = ((clientX - rect.left) / rect.width) * 100;
        if (pct < 0) pct = 0;
        if (pct > 100) pct = 100;
        return pct;
    }

    function indexFromPct(pct) {
        // Snap to nearest node.
        var bestI = 0;
        var bestDist = Infinity;
        for (var i = 0; i < nCount; i++) {
            var nodePct = pctFor(i);
            var dist = Math.abs(nodePct - pct);
            if (dist < bestDist) { bestDist = dist; bestI = i; }
        }
        return bestI;
    }

    function onMove(evt) {
        if (!dragging) return;
        if (evt.cancelable) evt.preventDefault();
        var pct = pctFromEvent(evt);
        var idx = indexFromPct(pct);
        if (idx !== currentIndex) setIndex(idx);
    }

    function onEnd() {
        if (!dragging) return;
        dragging = false;
        thumb.classList.remove('dragging');
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onEnd);
        document.removeEventListener('touchmove', onMove);
        document.removeEventListener('touchend', onEnd);
        document.removeEventListener('touchcancel', onEnd);
    }

    thumb.addEventListener('mousedown', function (e) {
        e.preventDefault();
        dragging = true;
        thumb.classList.add('dragging');
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onEnd);
    });

    thumb.addEventListener('touchstart', function (e) {
        dragging = true;
        thumb.classList.add('dragging');
        document.addEventListener('touchmove', onMove, { passive: false });
        document.addEventListener('touchend', onEnd);
        document.addEventListener('touchcancel', onEnd);
    }, { passive: true });

    // --- Keyboard ---
    trackWrap.addEventListener('keydown', function (e) {
        var handled = true;
        switch (e.key) {
            case 'ArrowLeft':
            case 'ArrowDown':
                setIndex(currentIndex - 1);
                break;
            case 'ArrowRight':
            case 'ArrowUp':
                setIndex(currentIndex + 1);
                break;
            case 'Home':
                setIndex(0);
                break;
            case 'End':
                setIndex(nCount - 1);
                break;
            default:
                handled = false;
        }
        if (handled) e.preventDefault();
    });
})();
