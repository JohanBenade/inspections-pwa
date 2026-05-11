#!/usr/bin/env python3
"""
Extract code segments needed for SMB latent integration.
Writes /tmp/smb_dump.txt.
Run from repo root: python3 extract_smb.py
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent


def extract_func_with_decorators(lines, def_line_idx):
    """Given index of `def name(...)` at column 0, return full top-level block."""
    start = def_line_idx
    while start > 0 and lines[start - 1].startswith("@"):
        start -= 1
    j = def_line_idx + 1
    while j < len(lines):
        ln = lines[j]
        if ln == "" or ln.startswith((" ", "\t")):
            j += 1
            continue
        break
    return "\n".join(lines[start:j]).rstrip() + "\n"


def extract_python_function(text, name):
    lines = text.split("\n")
    pat = re.compile(rf"^def {re.escape(name)}\(")
    for i, line in enumerate(lines):
        if pat.search(line):
            return extract_func_with_decorators(lines, i)
    return None


def extract_flask_route(text, url):
    lines = text.split("\n")
    route_pat = re.compile(rf"@[\w.]+\.route\(['\"]{re.escape(url)}['\"]")
    for i, line in enumerate(lines):
        if route_pat.search(line):
            j = i + 1
            while j < len(lines):
                if lines[j].startswith("def "):
                    return extract_func_with_decorators(lines, j)
                j += 1
    return None


def extract_jinja_block(text, start_regex):
    m = re.search(start_regex, text)
    if not m:
        return None
    start = m.start()
    pos = m.end()
    depth = 1
    if_re = re.compile(r"{%-?\s*if\b")
    endif_re = re.compile(r"{%-?\s*endif\s*-?%}")
    while pos < len(text) and depth > 0:
        next_if = if_re.search(text, pos)
        next_endif = endif_re.search(text, pos)
        if not next_endif:
            return None
        if next_if and next_if.start() < next_endif.start():
            depth += 1
            pos = next_if.end()
        else:
            depth -= 1
            pos = next_endif.end()
    return text[start:pos] + "\n"


TARGETS = [
    ("app/routes/analytics.py",             "function", "_build_brief_by_trade"),
    ("app/routes/analytics.py",             "route",    "/analytics/site-meeting-brief"),
    ("app/services/pdf_generator.py",       "function", "_fetch_latent_for_pdf"),
    ("app/services/pdf_generator.py",       "function", "encode_latent_photos"),
    ("app/templates/pdf/defects_list.html", "jinja",    r"\{%-?\s*if\s+latent_notes_list\b"),
    ("app/templates/pdf/defects_list.html", "jinja",    r"\{%-?\s*if\s+latent_summary\b"),
]


def main():
    out = []
    errors = 0
    for file_rel, kind, target in TARGETS:
        path = REPO / file_rel
        out.append(f"\n{'='*78}\nFILE: {file_rel}\nKIND: {kind}\nTARGET: {target}\n{'='*78}\n")
        if not path.exists():
            out.append(f"[ERROR] File not found: {path}\n")
            errors += 1
            continue
        text = path.read_text(encoding="utf-8")
        if kind == "function":
            block = extract_python_function(text, target)
        elif kind == "route":
            block = extract_flask_route(text, target)
        elif kind == "jinja":
            block = extract_jinja_block(text, target)
        else:
            block = None
        if block is None:
            out.append("[ERROR] Pattern not found.\n")
            errors += 1
        else:
            out.append(block)

    output = "".join(out)
    out_path = Path("/tmp/smb_dump.txt")
    out_path.write_text(output, encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"Size: {len(output)} chars, {output.count(chr(10))} lines")
    print(f"Segments extracted: {len(TARGETS) - errors}/{len(TARGETS)}")
    if errors:
        print(f"WARNING: {errors} extraction error(s) - check the dump file")
        sys.exit(1)
    print("Drag /tmp/smb_dump.txt into the chat.")


if __name__ == "__main__":
    main()
