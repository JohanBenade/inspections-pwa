#!/usr/bin/env python3
"""
Fix NameError: _FL_LABELS isn't at module scope in analytics.py — it's defined
locally inside other builder functions. Add a local definition in
_build_outstanding_items_data so it's self-contained.
"""
from pathlib import Path

ANALYTICS = Path("app/routes/analytics.py")
assert ANALYTICS.exists()

OLD = """def _build_outstanding_items_data(tenant_id):
    \"\"\"All open defects + outstanding latent, grouped Block -> Floor -> Unit -> Area.

    Live data (no snapshot freeze). For Ralph Rhoda's site teams to plan
    rectification sweeps. Latent notes are exploded into individual bullet
    items so each actionable line gets its own row.
    \"\"\"
    import sqlite3, re
    from datetime import datetime, timezone, timedelta

    conn = sqlite3.connect('/var/data/inspections.db')"""

NEW = """def _build_outstanding_items_data(tenant_id):
    \"\"\"All open defects + outstanding latent, grouped Block -> Floor -> Unit -> Area.

    Live data (no snapshot freeze). For Ralph Rhoda's site teams to plan
    rectification sweeps. Latent notes are exploded into individual bullet
    items so each actionable line gets its own row.
    \"\"\"
    import sqlite3, re
    from datetime import datetime, timezone, timedelta

    _FL_LABELS = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor', 3: '3rd Floor'}

    conn = sqlite3.connect('/var/data/inspections.db')"""


def main():
    src = ANALYTICS.read_text()

    if "_FL_LABELS = {0: 'Ground'" in src.split('def _build_outstanding_items_data', 1)[-1][:600]:
        print('[NO-OP] Local _FL_LABELS already present.')
        raise SystemExit(0)

    assert OLD in src, 'Anchor missing - drift'
    assert src.count(OLD) == 1, 'Anchor not unique'

    new_src = src.replace(OLD, NEW)
    assert "_FL_LABELS = {0: 'Ground'" in new_src

    ANALYTICS.write_text(new_src)
    print('[OK] Local _FL_LABELS added to _build_outstanding_items_data.')


if __name__ == '__main__':
    main()
