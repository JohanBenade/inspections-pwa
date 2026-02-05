import sqlite3
conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

merges = [
    ("Sand in hinges", ["Sand in hinge", "Hinges have sand"]),
    ("Wi-Fi repeater not installed", ["Wi-Fi Repeater not installed", "WIFI Repeater not installed"]),
    ("Locks installed upside down", ["Locks are installed upside down", "Locks installed ups and down (One lock facing up and the other facing down when opening)", "Locks installed upside down (one lock facing up and the other facing down when opening)", "Locks upside down"]),
    ("Arm cover plate loose", ["Arm cover plate is loose", "Arm plate is loose"]),
    ("Rose cover plate loose", ["Rose cover plate is loose", "Rose plate is loose"]),
    ("Inconsistent grout colour", ["Grout has inconsistent colour", "Grout has an inconsistent colour"]),
    ("Damaged paint as indicated", ["Paint is damaged as indicated"]),
    ("Sand in runners", ["Sand in runner", "Runners have sand", "Runners have sand in them"]),
    ("Door stop loose", ["Door stop is loose", "Door stopper is loose"]),
    ("Door stop not installed", ["B.I.C door stopper not installed", "No door stop (by B.I.C.)", "No door stop by B.I.C.", "Door does not hit against the door stop / No door stop by B.I.C."]),
    ("WC indicator not working", ["WC indicator bolt and thumb turn malfunctions", "WC indicator does not turn to show right colours", "WC indicator does not work/indicate colours", "Bathroom lock malfunctions (colours are switched)"]),
]

print("=== WASHING DEFECT DESCRIPTIONS ===\n")
total = 0
for canonical, variants in merges:
    placeholders = ','.join(['?' for _ in variants])
    cur.execute(f"UPDATE defect SET original_comment = ? WHERE original_comment IN ({placeholders})", [canonical] + variants)
    if cur.rowcount > 0:
        print(f"{cur.rowcount:3} -> {canonical}")
        total += cur.rowcount

conn.commit()
print(f"\nTotal updated: {total}")

cur.execute("SELECT COUNT(DISTINCT original_comment) FROM defect WHERE tenant_id = 'MONOGRAPH'")
print(f"Unique descriptions: 186 -> {cur.fetchone()[0]}")

conn.close()
print("\nDONE")
