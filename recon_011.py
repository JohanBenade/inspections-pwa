import sqlite3
c=sqlite3.connect('/var/data/inspections.db');c.row_factory=sqlite3.Row;q=c.cursor()
U,T='37abd384','MONOGRAPH'

# Find C1 and C2 inspection IDs
ci={r['cycle_number']:r['id'] for r in q.execute("SELECT id,cycle_number FROM inspection WHERE unit_id=? AND tenant_id=? ORDER BY cycle_number",[U,T])}
print(f"\nInspections: C1={ci.get(1)}  C2={ci.get(2)}")

print('\n=== C1 ITEM STATUS ===')
for r in q.execute("SELECT status,COUNT(*) n FROM inspection_item WHERE inspection_id=? GROUP BY status ORDER BY status",[ci[1]]):
    print(f"  {r['status']:<18}{r['n']}")

print('\n=== C2 ITEM STATUS ===')
for r in q.execute("SELECT status,COUNT(*) n FROM inspection_item WHERE inspection_id=? GROUP BY status ORDER BY status",[ci[2]]):
    print(f"  {r['status']:<18}{r['n']}")

print('\n=== (2)(4) DEFECTS B/FWD (raised at C1) ===')
for r in q.execute("""SELECT CASE WHEN addressed_cycle_number IS NULL THEN 'UNMARKED (no action yet)' WHEN addressed_cycle_number=2 AND status='open' THEN 'MARKED still-open' WHEN addressed_cycle_number=2 AND status='cleared' THEN 'MARKED cleared' ELSE 'other' END b,COUNT(*) n FROM defect WHERE unit_id=? AND raised_cycle_number<2 GROUP BY b ORDER BY b""",[U]):
    print(f"  {r['b']:<28}{r['n']}")

print('\n=== (3)(5) ITEMS EXCLUDED AT C1 - now at C2 ===')
r=q.execute("""SELECT c2.status, COUNT(*) n FROM inspection_item c1 JOIN inspection_item c2 ON c2.item_template_id=c1.item_template_id AND c2.inspection_id=? WHERE c1.inspection_id=? AND c1.status='skipped' GROUP BY c2.status ORDER BY c2.status""",[ci[2],ci[1]]).fetchall()
tot=0
for row in r:
    print(f"  C1-skipped, C2-{row['status']:<16} {row['n']}")
    tot+=row['n']
print(f"  C1-skipped TOTAL                {tot}")

print('\n=== (1) C2 PENDING ITEMS - origin breakdown ===')
for r in q.execute("""SELECT CASE WHEN c1.status='skipped' THEN 'was excluded at C1' WHEN c1.status='not_to_standard' THEN 'was NTS at C1 (had defect)' WHEN c1.status='ok' THEN 'was ok at C1' ELSE 'C1='||COALESCE(c1.status,'no-row') END origin,COUNT(*) n FROM inspection_item c2 LEFT JOIN inspection_item c1 ON c1.item_template_id=c2.item_template_id AND c1.inspection_id=? WHERE c2.inspection_id=? AND c2.status='pending' GROUP BY origin ORDER BY origin""",[ci[1],ci[2]]):
    print(f"  {r['origin']:<30}{r['n']}")
c.close()
