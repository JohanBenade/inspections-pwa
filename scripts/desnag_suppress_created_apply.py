#!/usr/bin/env python3
"""
Suppress "Created {batch_created}" segment from De-snag Report meta line.

Template-only. Python helper still computes batch_created (becomes orphan,
swept in deferred dead-code cleanup).

Run from repo root: python3 scripts/desnag_suppress_created_apply.py
"""

from pathlib import Path

DESNAG = Path("app/templates/analytics/batch_desnag.html")


def replace_once(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    assert count == 1, f"{label}: expected 1 match in {path}, found {count}"
    path.write_text(text.replace(old, new))
    after = path.read_text()
    assert after.count(new) == 1, f"{label}: post-write missing new string"
    assert after.count(old) == 0, f"{label}: old string still present"
    print(f"OK  {label}")


replace_once(
    DESNAG,
    '<div class="report-meta">Created {{ batch_created }} &middot; Live data &middot; {{ snapshot_label }}</div>',
    '<div class="report-meta">Live data &middot; {{ snapshot_label }}</div>',
    "desnag suppress 'Created' date",
)

print("\nChange applied. Verify with grep, then commit.")
