#!/usr/bin/env python3
"""De-snag Report - Commit 1: insert helper + 2 routes into analytics.py.

Run from repo root:
    python3 scripts/desnag_commit1_apply.py

Idempotent guard: refuses to run if De-snag code already present.
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(REPO_ROOT, 'app', 'routes', 'analytics.py')
FRAGMENT = os.path.join(REPO_ROOT, 'scripts', 'desnag_commit1_fragment.txt')

# End of outstanding_items_pdf route - unique because of the Outstanding_Items_ filename.
ANCHOR = "    resp.headers['Content-Disposition'] = 'attachment; filename=Outstanding_Items_{}.pdf'.format(today_iso)\n    return resp"

def main():
    if not os.path.exists(TARGET):
        sys.exit("[FAIL] Target not found: {}".format(TARGET))
    if not os.path.exists(FRAGMENT):
        sys.exit("[FAIL] Fragment not found: {}".format(FRAGMENT))

    with open(TARGET, 'r') as f:
        content = f.read()

    # Pre-asserts
    count = content.count(ANCHOR)
    if count != 1:
        sys.exit("[FAIL] Anchor count = {} (expected 1). Aborting.".format(count))
    print("[OK] Anchor found exactly once")

    if '_build_batch_desnag_data' in content:
        sys.exit("[FAIL] '_build_batch_desnag_data' already present in analytics.py - aborting.")
    if 'batch_desnag_view' in content:
        sys.exit("[FAIL] 'batch_desnag_view' already present - aborting.")
    if 'batch_desnag_pdf' in content:
        sys.exit("[FAIL] 'batch_desnag_pdf' already present - aborting.")
    print("[OK] No pre-existing De-snag code")

    with open(FRAGMENT, 'r') as f:
        fragment = f.read()
    print("[OK] Fragment loaded: {} bytes".format(len(fragment)))

    new_content = content.replace(ANCHOR, ANCHOR + fragment, 1)

    # Post-asserts
    if new_content.count('def _build_batch_desnag_data(') != 1:
        sys.exit("[FAIL] Helper def count != 1 after insert")
    if new_content.count("@analytics_bp.route('/report/desnag/<batch_id>')") != 1:
        sys.exit("[FAIL] View route count != 1 after insert")
    if new_content.count("@analytics_bp.route('/report/desnag/<batch_id>/pdf')") != 1:
        sys.exit("[FAIL] PDF route count != 1 after insert")
    if new_content.count('def batch_desnag_view(batch_id):') != 1:
        sys.exit("[FAIL] View function def count != 1 after insert")
    if new_content.count('def batch_desnag_pdf(batch_id):') != 1:
        sys.exit("[FAIL] PDF function def count != 1 after insert")
    print("[OK] All 5 post-insert assertions passed")

    with open(TARGET, 'w') as f:
        f.write(new_content)
    print("[OK] Wrote {} bytes ({:+d} delta) to {}".format(
        len(new_content), len(new_content) - len(content), TARGET))

if __name__ == '__main__':
    main()
