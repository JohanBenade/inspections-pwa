#!/usr/bin/env python3
"""
Compact top-nav to prevent text-within-item wrapping on team_lead view.

Touches two mechanisms:
1. base.html — Tailwind utility classes (text-sm -> text-xs, space-x-4 -> space-x-3)
2. 4 standalone report templates — inline .top-nav CSS (font-size 14px -> 12px,
   .top-nav .left gap 22px -> 12px)

Out of scope: site_meeting_brief.html, data_quality/*.html — different mechanisms,
deferred to a follow-up.

Run from repo root: python3 scripts/nav_compact_apply.py
"""

from pathlib import Path

BASE = Path("app/templates/base.html")
REPORT_TEMPLATES = [
    Path("app/templates/analytics/briefing.html"),
    Path("app/templates/analytics/batch_desnag.html"),
    Path("app/templates/analytics/outstanding_items.html"),
    Path("app/templates/analytics/report_batch.html"),
]


def replace_all(path, old, new, label):
    """Replace every occurrence of old with new. Asserts at least 1 match,
    no leftovers, and post-write count matches pre-write count."""
    text = path.read_text()
    count = text.count(old)
    assert count > 0, f"{label}: no matches found in {path}"
    path.write_text(text.replace(old, new))
    after = path.read_text()
    assert after.count(new) >= count, f"{label}: post-write missing replacements"
    assert after.count(old) == 0, f"{label}: old string still present"
    print(f"OK  {label} ({count} repl)")


def replace_once(path, old, new, label):
    """Replace exactly one occurrence. Asserts match count == 1."""
    text = path.read_text()
    count = text.count(old)
    assert count == 1, f"{label}: expected 1 match in {path}, found {count}"
    path.write_text(text.replace(old, new))
    after = path.read_text()
    assert after.count(new) == 1, f"{label}: post-write missing new string"
    assert after.count(old) == 0, f"{label}: old still present"
    print(f"OK  {label}")


# -- base.html (Tailwind) --

# 1. All nav links: text-sm -> text-xs
replace_all(
    BASE,
    'class="text-sm text-gray-300 hover:text-white"',
    'class="text-xs text-gray-300 hover:text-white"',
    "base.html: nav links text-sm -> text-xs",
)

# 2. Nav-links container gap: space-x-4 -> space-x-3
replace_once(
    BASE,
    'class="hidden md:flex items-center space-x-4"',
    'class="hidden md:flex items-center space-x-3"',
    "base.html: nav-links container gap",
)

# 3. Logout link: text-sm -> text-xs
replace_once(
    BASE,
    'class="hidden md:inline text-sm text-gray-300 hover:text-white"',
    'class="hidden md:inline text-xs text-gray-300 hover:text-white"',
    "base.html: logout link text-sm -> text-xs",
)

# 4. User name span: text-sm -> text-xs
replace_once(
    BASE,
    'class="text-sm text-gray-300 hidden sm:inline"',
    'class="text-xs text-gray-300 hidden sm:inline"',
    "base.html: user name text-sm -> text-xs",
)


# -- 4 standalone report templates (inline CSS) --

TOPNAV_FONT_OLD = "font-family: 'DM Sans', system-ui, sans-serif; font-size: 14px;"
TOPNAV_FONT_NEW = "font-family: 'DM Sans', system-ui, sans-serif; font-size: 12px;"

TOPNAV_GAP_OLD = ".top-nav .left { display: flex; align-items: center; gap: 22px; flex-wrap: wrap; }"
TOPNAV_GAP_NEW = ".top-nav .left { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }"

for tpl in REPORT_TEMPLATES:
    replace_once(tpl, TOPNAV_FONT_OLD, TOPNAV_FONT_NEW, f"{tpl.name}: top-nav font 14px -> 12px")
    replace_once(tpl, TOPNAV_GAP_OLD, TOPNAV_GAP_NEW, f"{tpl.name}: top-nav gap 22px -> 12px")


print("\nAll nav changes applied. Verify with grep, then commit.")
