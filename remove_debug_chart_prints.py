#!/usr/bin/env python3
path = 'app/routes/analytics.py'
with open(path, 'r') as f:
    content = f.read()

old1 = """        steps.reverse()
        print(f"[DEBUG-CHART] snapshot_sast={snapshot_sast} snapshot_str={snapshot_str} anchor={anchor} steps={[s.strftime('%Y-%m-%d %H:%M:%S') for s in steps]}", flush=True)
        
        for p in steps:"""

new1 = """        steps.reverse()

        for p in steps:"""

assert old1 in content, "Removal 1: old block not found"
content = content.replace(old1, new1)

old2 = """                [tenant_id, p_str, snapshot_str], one=True)
            print(f"[DEBUG-CHART] p_str={p_str} gate={gate_units['c']} raised={raised_row['c'] if raised_row else 0} cleared={cleared_row['c'] if cleared_row else 0}", flush=True)
            trend_points.append({"""

new2 = """                [tenant_id, p_str, snapshot_str], one=True)
            trend_points.append({"""

assert old2 in content, "Removal 2: old block not found"
content = content.replace(old2, new2)

assert "DEBUG-CHART" not in content, "DEBUG-CHART still present after replacements"

with open(path, 'w') as f:
    f.write(content)

print("OK: both DEBUG-CHART prints removed")
