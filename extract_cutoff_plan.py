#!/usr/bin/env python3
"""
Extraction script for SMB cutoff-shift planning + review_submitted_at setter verification.

Extracts in one round-trip:
  PART 1: _build_pipeline_report_data function body (analytics.py)
           -> snap_str / snapshot_str / prev_cutoff computation + live mode branch
  PART 2: Codebase-wide snap_str / snapshot_str / prev_cutoff assignments
           -> confirms no parallel snapshot calc exists elsewhere
  PART 3: Every function in approvals.py whose body references review_submitted_at
           -> answers the "interpretation A vs B" question
  PART 4: Codebase-wide review_submitted_at references with SQL mutation context
           -> sanity check that setter sites aren't outside approvals.py

Output:
  /tmp/cutoff_plan_dump.txt  (canonical)
  ~/Desktop/cutoff_plan_dump.txt  (Finder-visible copy for drag-and-drop)

Run from inspections-pwa repo root.
"""

import os
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
APP_DIR = REPO_ROOT / "app"
OUT_TMP = Path("/tmp/cutoff_plan_dump.txt")
OUT_DESKTOP = Path(os.path.expanduser("~/Desktop/cutoff_plan_dump.txt"))

assert APP_DIR.exists(), f"Expected {APP_DIR} to exist. Run from inspections-pwa repo root."


def extract_function(filepath, fn_name, max_lines=800):
    """Extract a top-level Python function body. Walks from def to next top-level def/class."""
    if not filepath.exists():
        return f"[FILE NOT FOUND: {filepath}]"
    lines = filepath.read_text().splitlines()
    start = None
    indent = None
    for i, line in enumerate(lines):
        m = re.match(r'^(\s*)def\s+' + re.escape(fn_name) + r'\b', line)
        if m:
            start = i
            indent = len(m.group(1))
            break
    if start is None:
        return f"[FUNCTION {fn_name} NOT FOUND in {filepath.name}]"
    end = start + 1
    while end < len(lines) and (end - start) < max_lines:
        line = lines[end]
        if line.strip() == '':
            end += 1
            continue
        m = re.match(r'^(\s*)(def|class)\s+', line)
        if m and len(m.group(1)) <= indent:
            break
        end += 1
    return "\n".join(f"L{i+1}: {lines[i]}" for i in range(start, end))


def find_functions_containing(filepath, pattern):
    """Return list of (name, start_line, end_line) for top-level functions whose body matches pattern."""
    if not filepath.exists():
        return []
    lines = filepath.read_text().splitlines()
    pat = re.compile(pattern)
    fn_defs = []
    for i, line in enumerate(lines):
        m = re.match(r'^def\s+(\w+)', line)
        if m:
            fn_defs.append((m.group(1), i))
    out = []
    for idx, (name, start) in enumerate(fn_defs):
        end = fn_defs[idx + 1][1] if idx + 1 < len(fn_defs) else len(lines)
        body = "\n".join(lines[start:end])
        if pat.search(body):
            out.append((name, start, end))
    return out


def grep_with_context(pattern, files, before=3, after=4):
    """Grep across files. Return formatted matches with file:line headers and a context window."""
    out_blocks = []
    pat = re.compile(pattern)
    for f in files:
        try:
            lines = f.read_text().splitlines()
        except Exception:
            continue
        hits = []
        for i, line in enumerate(lines):
            if pat.search(line):
                lo = max(0, i - before)
                hi = min(len(lines), i + after + 1)
                ctx = []
                for j in range(lo, hi):
                    marker = ">>>" if j == i else "   "
                    ctx.append(f"  {marker} L{j+1}: {lines[j]}")
                hits.append("\n".join(ctx))
        if hits:
            rel = f.relative_to(REPO_ROOT)
            out_blocks.append(f"\n--- {rel} ---\n" + "\n\n".join(hits))
    return "\n".join(out_blocks) if out_blocks else "[NO MATCHES]"


py_files = sorted(APP_DIR.rglob("*.py"))
analytics_path = APP_DIR / "routes" / "analytics.py"
approvals_path = APP_DIR / "routes" / "approvals.py"

out = []
out.append("=" * 80)
out.append("CUTOFF PLAN DUMP")
out.append("=" * 80)
out.append(f"Repo: {REPO_ROOT}")
out.append(f"Python files scanned: {len(py_files)}")
out.append("")

# PART 1
out.append("=" * 80)
out.append("PART 1: _build_pipeline_report_data function body (analytics.py)")
out.append("=" * 80)
out.append(extract_function(analytics_path, "_build_pipeline_report_data", max_lines=1000))
out.append("")

# PART 2
out.append("=" * 80)
out.append("PART 2: snap_str / snapshot_str / prev_cutoff assignments (codebase-wide)")
out.append("=" * 80)
out.append(grep_with_context(
    r'\b(snap_str|snapshot_str|prev_cutoff|_prev_cutoff)\s*=(?!=)',
    py_files, before=3, after=4
))
out.append("")

# PART 3
out.append("=" * 80)
out.append("PART 3: Functions in approvals.py containing 'review_submitted_at'")
out.append("=" * 80)
if not approvals_path.exists():
    out.append(f"[FILE NOT FOUND: {approvals_path}]")
else:
    matching_fns = find_functions_containing(approvals_path, r'review_submitted_at')
    if not matching_fns:
        out.append("[NO FUNCTIONS in approvals.py reference review_submitted_at]")
    else:
        out.append(f"Found {len(matching_fns)} function(s): " + ", ".join(n for n, _, _ in matching_fns))
        out.append("")
        for name, start, end in matching_fns:
            out.append(f"--- approvals.py :: {name}() (lines {start+1} to {end}) ---")
            out.append(extract_function(approvals_path, name, max_lines=500))
            out.append("")
out.append("")

# PART 4
out.append("=" * 80)
out.append("PART 4: review_submitted_at references with SQL mutation context (codebase-wide)")
out.append("=" * 80)
out.append("Filter: line contains 'review_submitted_at' AND a SQL mutation keyword")
out.append("(UPDATE / SET / INSERT) appears within +/- 5 lines.")
out.append("")
mut_keywords = re.compile(r'\b(UPDATE|SET|INSERT)\b')
rsa_pat = re.compile(r'review_submitted_at')
found_any = False
for f in py_files:
    try:
        lines = f.read_text().splitlines()
    except Exception:
        continue
    hits = []
    for i, line in enumerate(lines):
        if rsa_pat.search(line):
            wlo = max(0, i - 5)
            whi = min(len(lines), i + 6)
            window = "\n".join(lines[wlo:whi])
            if mut_keywords.search(window):
                clo = max(0, i - 5)
                chi = min(len(lines), i + 8)
                ctx = []
                for j in range(clo, chi):
                    marker = ">>>" if j == i else "   "
                    ctx.append(f"  {marker} L{j+1}: {lines[j]}")
                hits.append("\n".join(ctx))
    if hits:
        found_any = True
        rel = f.relative_to(REPO_ROOT)
        out.append(f"--- {rel} ---")
        for h in hits:
            out.append(h)
            out.append("")
if not found_any:
    out.append("[NO MUTATION-CONTEXT MATCHES]")

# Write
OUT_TMP.parent.mkdir(parents=True, exist_ok=True)
OUT_TMP.write_text("\n".join(out))
try:
    OUT_DESKTOP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT_TMP, OUT_DESKTOP)
    desktop_status = f"Desktop copy: {OUT_DESKTOP}"
except Exception as e:
    desktop_status = f"Desktop copy FAILED: {e}"

print(f"Dump written: {OUT_TMP} ({OUT_TMP.stat().st_size:,} bytes)")
print(desktop_status)
