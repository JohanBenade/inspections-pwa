"""
Defect Description Cleanup Script
==================================
Standardises defect descriptions across defect, inspection_item, and defect_library tables.
Deletes Wi-Fi repeater defects (standard exclusion item that should never have been imported).

Usage (Render console):
    python3 scripts/defect_cleanup.py --dry-run    # Preview changes, touch nothing
    python3 scripts/defect_cleanup.py --execute     # Run the cleanup

Tables affected:
    defect.original_comment       - 627 records standardised, 12 deleted
    inspection_item.comment       - matching records standardised, 12 reset to skipped
    defect_library.description    - matching entries standardised, 1 deleted

Safe to run multiple times - uses exact string matching, already-clean records are skipped.
"""
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = '/var/data/inspections.db'
TENANT = 'MONOGRAPH'

# ============================================================
# RENAME MAP: old_description -> new_description
# Groups 1-55 from the approved cleanup mapping
# ============================================================
RENAME_MAP = {
    # 01: Chipped tile
    "Tiles are chipped as indicated": "Chipped tile as indicated",
    "Chipped tiles as indicated": "Chipped tile as indicated",
    "Tile chipped as indicated": "Chipped tile as indicated",
    "The paint is chipped as indicated": "Chipped tile as indicated",
    "Chipped tile": "Chipped tile as indicated",
    "Chipped tiles": "Chipped tile as indicated",
    "Stove splash back tile is chipped": "Chipped tile as indicated",
    "Splash back wrap at sink is chipped": "Chipped tile as indicated",
    "Chipped tile next to the counter seating": "Chipped tile as indicated",
    "Chipped tile by bedroom A and B": "Chipped tile as indicated",
    "Chipped tile next to study desk": "Chipped tile as indicated",
    "Chipped tile by the bathroom door": "Chipped tile as indicated",
    "Chipped tile at sink splash back": "Chipped tile as indicated",
    "Tile cracked/chipped by door stop": "Chipped tile as indicated",

    # 02: Broken/cracked tile
    "Broken tiles at the doorstep": "Broken/cracked tile as indicated",
    "Broken tiles as indicated": "Broken/cracked tile as indicated",
    "Hollow and broken tile under the study desk": "Broken/cracked tile as indicated",

    # 03: Hollow tile
    "Hollow tile next to the bathroom": "Hollow tile as indicated",
    "Hollow tile behind door as indicated": "Hollow tile as indicated",
    "Hollow tile behind door": "Hollow tile as indicated",

    # 04: Locks upside down
    "Locks installed ups and down (One lock facing up and the other facing down when opening)": "Locks installed upside down",

    # 05: Grout at skirting/floor
    "There is grout missing in between the tile skirting and the floor": "Missing grout between tile skirting and floor",
    "Gap between tile skirting and floor as indicated": "Missing grout between tile skirting and floor",
    "Missing grout between floor and tile skirting": "Missing grout between tile skirting and floor",
    "Grout missing in between floor and tile skirting": "Missing grout between tile skirting and floor",
    "Grout missing between tile skirting and floor": "Missing grout between tile skirting and floor",
    "Gaps between tile skirting and the floor": "Missing grout between tile skirting and floor",
    "Missing grout in between tile skirting and floor": "Missing grout between tile skirting and floor",
    "Missing grout in between floor and tile skirting": "Missing grout between tile skirting and floor",
    "Gaps between tile skirting and floor, no grout installed": "Missing grout between tile skirting and floor",
    "No grout in between tile skirtings": "Missing grout between tile skirting and floor",
    "There are gaps in between tile skirting and floor under the stove, sink pack and bin drawer": "Missing grout between tile skirting and floor",

    # 06: Grout colour
    "Grout colour is not consistent": "Inconsistent grout colour",
    "The grout colour is not consistent as indicated": "Inconsistent grout colour",
    "The floor tile set out is not consistent": "Inconsistent grout colour",
    "Inconsistent tile set out": "Inconsistent grout colour",
    "Grout in the shower is not dark grey": "Grout colour incorrect in shower",

    # 07: Grout at tile trim
    "There is missing grout in between tile trim and tiles in the duct wall corner": "Missing grout at tile trim",
    "Missing grout between tiles and tile trim at stove splash back top and side": "Missing grout at tile trim",
    "Missing grout between tile trim and splash back tile": "Missing grout at tile trim",
    "There is missing grout in between tile trim and tiles in the shower step": "Missing grout at tile trim",
    "There is missing grout in between tile trim and tiles in window reveal": "Missing grout at tile trim",
    "Tile trim on the duct wall corner does not have sufficient grout": "Missing grout at tile trim",
    "Tile trim on duct wall corner does not have sufficient grout": "Missing grout at tile trim",
    "Gap between tiles and tile trim at window reveal": "Missing grout at tile trim",
    "Gap between tiles and tile trim at duct wall corner": "Missing grout at tile trim",
    "Missing grout in between tiles and tile trim as indicated": "Missing grout at tile trim",

    # 08: Grout between tiles
    "Grout missing between tiles": "Missing grout between tiles",
    "Grout missing in between tiles": "Missing grout between tiles",
    "Grout missing in between tiles as indicated": "Missing grout between tiles",
    "Missing grout in between tiles": "Missing grout between tiles",
    "Grout missing in between tiles at sink splash back": "Missing grout between tiles",
    "Gaps between tiles at right corner of shower, no grout installed": "Missing grout between tiles",
    "Gap between tiles at corner by shower wall": "Missing grout between tiles",
    "Tiles on the reveal have no grout": "Missing grout between tiles",

    # 09: Grout damaged
    "Grout is damaged at sink splash back": "Grout damaged as indicated",
    "Damaged grout as indicated": "Grout damaged as indicated",
    "Grout has holes in it": "Grout damaged as indicated",
    "Grout has gaps": "Grout damaged as indicated",
    "Holes in grout as indicated": "Grout damaged as indicated",
    "Holes in grout": "Grout damaged as indicated",
    "Missing grout as indicated": "Grout damaged as indicated",
    "Grout missing by door": "Grout damaged as indicated",
    "Grout missing in between tile and tile skirting": "Grout damaged as indicated",
    "Missed grout dove grey fill lines by unit main door": "Grout damaged as indicated",
    "Grout dove grey needed behind the waste pipe": "Grout damaged as indicated",

    # 10: Rubber studs on frame
    "Screw-like rubbers on door frame damage the door paint": "Rubber studs on frame damaging door finish",
    "Scratches on door caused by rubber stud on frame hitting door": "Rubber studs on frame damaging door finish",
    "Rubber studs that need to be removed in the frame because they damage the door": "Rubber studs on frame damaging door finish",
    "Screw-like rubber studs to be removed before further door damage": "Rubber studs on frame damaging door finish",
    "Screw-like rubber stud damaging door finish": "Rubber studs on frame damaging door finish",
    "Screw like rubber studs damaging door finish to be removed": "Rubber studs on frame damaging door finish",
    "Rubber-like studs to be removed as they damage the door finish": "Rubber studs on frame damaging door finish",
    "Rubber studs to be removed as they are damaging door finish": "Rubber studs on frame damaging door finish",
    "Rubber studs on frame damage the door finish": "Rubber studs on frame damaging door finish",
    "Remove screw-like rubbers on door frame as they damage the door paint": "Rubber studs on frame damaging door finish",
    "Remove screw-like rubbers on door frame as they damage door as it keeps closing": "Rubber studs on frame damaging door finish",
    "Remove screw-like rubber stud on frame to avoid damaging door finish": "Rubber studs on frame damaging door finish",

    # 11: Door stop
    "B.I.C door stopper not installed": "Door stop not installed",
    "No door stopper at B.I.C. door": "Door stop not installed",
    "No door stopper by B.I.C. door": "Door stop not installed",
    "Door hits door stopper plate, not the rubber": "Door hits stop plate, not rubber",
    "Door hits door stopper at the steel part instead of the rubber part": "Door hits stop plate, not rubber",
    "Door hits against steel part of door stop not the rubber": "Door hits stop plate, not rubber",
    "Door does not touch the rubber on door stop": "Door hits stop plate, not rubber",
    "Door stopper installed far from door, might obstruct fridge usage": "Door stop positioned incorrectly",

    # 12: Ceiling light
    "Ceiling mounted light only has one bulb": "Ceiling light: one bulb missing",
    "There is only one light bulb": "Ceiling light: one bulb missing",
    "Ceiling mounted light has one bulb": "Ceiling light: one bulb missing",
    "Ceiling mounted light cover needs to be cleaned": "Ceiling light cover needs cleaning",
    "Ceiling mounted light needs to be cleaned": "Ceiling light cover needs cleaning",

    # 13: Skirting to B.I.C.
    "Tile skirting not legibly fixed to B.I.C underside": "Tile skirting not flush with B.I.C. underside",
    "Tile skirting not flushed well to cupboard underside": "Tile skirting not flush with B.I.C. underside",
    "Tile skirting not flushed well to B.I.C. underside": "Tile skirting not flush with B.I.C. underside",
    "Tile skirting not flushed well to B.I.C underside": "Tile skirting not flush with B.I.C. underside",
    "Tile skirting not flushed legibly to cupboard underside and does not connect tiles well at corner": "Tile skirting not flush with B.I.C. underside",
    "Tile skirting needs grout filling between B.I.C. underside": "Tile skirting not flush with B.I.C. underside",

    # 14: Gap skirting/B.I.C.
    "There is a gap in between tile skirting and B.I.C": "Gap between tile skirting and B.I.C.",
    "Gaps between tile skirting and B.I.C": "Gap between tile skirting and B.I.C.",
    "Gaps between B.I.C and tile skirting": "Gap between tile skirting and B.I.C.",
    "Gap under B.I.C. and tile skirting": "Gap between tile skirting and B.I.C.",
    "Gap between B.I.C. and tile skirting": "Gap between tile skirting and B.I.C.",
    "Gap between counter top and B.I.C": "Gap between tile skirting and B.I.C.",
    "There is a gap between tile skirting and B.I.C": "Gap between tile skirting and B.I.C.",

    # 15: B.I.C. shelf supports
    "Plastic shelf supporters inside B.I.C cracked": "B.I.C. shelf supports cracked",
    "Plastic shelf supporters inside B.I.C is cracked": "B.I.C. shelf supports cracked",
    "Plastic shelf supporters cracked due to being screwed in too much": "B.I.C. shelf supports cracked",

    # 16: B.I.C. clothing hanger
    "Clothing hanger inside B.I.C is not installed": "B.I.C. clothing hanger not installed",

    # 17: Paint damaged/chipped
    "The paint is chipped as indicated": "Damaged paint as indicated",
    "Paint is chipped as indicated": "Damaged paint as indicated",
    "Paint is chipped and dirty as indicated": "Damaged paint as indicated",
    "Paint is chipped above the door": "Damaged paint as indicated",
    "Paint finish is chipped as indicated": "Damaged paint as indicated",
    "Paint not clean and damaged": "Damaged paint as indicated",
    "Damaged paint near light switch as indicated": "Damaged paint as indicated",

    # 18: Paint peeling
    "Peeling paint as indicated": "Paint peeling as indicated",
    "Paint is peeling off as indicated": "Paint peeling as indicated",
    "Paint peeling off the door": "Paint peeling as indicated",
    "Paint peeling off under striker plate": "Paint peeling as indicated",
    "Wall paint peeling off by towel rail": "Paint peeling as indicated",
    "Orchid bay paint is peeling off as indicated": "Paint peeling as indicated",

    # 19: Overlapping paint
    "There is overlapping paint on the frame as indicated": "Overlapping paint as indicated",
    "There is overlapping paint": "Overlapping paint as indicated",
    "Paints are overlapping": "Overlapping paint as indicated",
    "Paint is overlapping as indicated": "Overlapping paint as indicated",
    "Has paint overlaps": "Overlapping paint as indicated",
    "Paint overlaps near window": "Overlapping paint as indicated",
    "Overlapping paint on door": "Overlapping paint as indicated",

    # 20: Paint stains/marks
    "Smudge paint on tile": "Paint stains as indicated",
    "Has paint marks": "Paint stains as indicated",
    "Handle has grey paint smudge": "Paint stains as indicated",
    "Paint on outside has white smudges": "Paint stains as indicated",
    "White paint stains on door exterior as indicated": "Paint stains as indicated",
    "Has paint droplets": "Paint stains as indicated",
    "Smudges paint on floor tile": "Paint stains as indicated",
    "Paint stains on door frame": "Paint stains as indicated",
    "Paint stains by floating shelf": "Paint stains as indicated",
    "Paint stains by DB and left door, needs cleaning inside": "Paint stains as indicated",
    "Paint stain inside B.I.C.": "Paint stains as indicated",
    "White paint stains as indicated": "Paint stains as indicated",
    "White paint marks as indicated": "Paint stains as indicated",
    "White paint on study desk": "Paint stains as indicated",
    "Grey paint marks on door finish": "Paint stains as indicated",
    "Green paint stains on orchid bay paint": "Paint stains as indicated",
    "Paint on outside has white gaps": "Paint stains as indicated",
    "Paint on burglar bars": "Paint stains as indicated",
    "Paint on Floating shelf finish": "Paint stains as indicated",
    "Paint on study desk finish": "Paint stains as indicated",
    "Paint on B.I.C. finish": "Paint stains as indicated",
    "Paint has marks as indicated": "Paint stains as indicated",
    "Paint has dirt marks as indicated": "Paint stains as indicated",
    "Orchid bay paint stains on floating shelf": "Paint stains as indicated",
    "Orchid bay paint has an unpainted patch as indicated": "Paint stains as indicated",
    "Black stain on door exterior": "Paint stains as indicated",
    "Dusty white stain above door": "Paint stains as indicated",
    "Stains all over floating shelf wall": "Paint stains as indicated",
    "Floating shelf has paint stains": "Paint stains as indicated",
    "Frame stained with yellowish/lighter green shade coloured paint": "Paint stains as indicated",
    "Yellow paint stain inside left pack": "Paint stains as indicated",

    # 21: Paint scratched
    "Paint scratched/scuffed": "Paint scratched as indicated",
    "Ceiling paint scratched": "Paint scratched as indicated",
    "Paint is scratched as indicated": "Paint scratched as indicated",
    "Paint-orchid bay is scratched": "Paint scratched as indicated",
    "Wall paint orchid bay is scratched as indicated": "Paint scratched as indicated",
    "Paint-orchid bay is chipped": "Paint scratched as indicated",

    # 22: Uneven paint
    "Uneven paint above door, patches of paint and not full finish": "Uneven paint application as indicated",
    "Uneven paint application by window 3": "Uneven paint application as indicated",
    "Uneven paint stains behind panel heater": "Uneven paint application as indicated",
    "Paint is not applied properly at the top of the door": "Uneven paint application as indicated",
    "Paint is not applied equally as indicated": "Uneven paint application as indicated",
    "There is inconsistency in paint application": "Uneven paint application as indicated",
    "Inconsistent paint application": "Uneven paint application as indicated",
    "Has inconsistent paint application": "Uneven paint application as indicated",
    "Top part not painted as indicated": "Uneven paint application as indicated",
    "Unpainted patch under study desk": "Uneven paint application as indicated",
    "Orchid bay paint has chipped plaster above plug point": "Uneven paint application as indicated",

    # 23: Paint needs cleaning
    "Paint needs to be cleaned": "Paint needs cleaning",
    "Paint needs to be cleaned as indicated": "Paint needs cleaning",
    "Paint on outside the door needs to be cleaned": "Paint needs cleaning",
    "Door paint needs to be cleaned": "Paint needs cleaning",
    "Stains to be cleaned off door": "Paint needs cleaning",

    # 24: Wall needs painting
    "Wall needs to be painted by W1 and by DB": "Wall needs repainting as indicated",
    "Carcass back wall needs to be painted": "Wall needs repainting as indicated",
    "Door paint needs to be reapplied where indicated": "Wall needs repainting as indicated",
    "Door upside not finished well, needs repaint/one more coat": "Wall needs repainting as indicated",
    "Paint on wall looks wet": "Wall needs repainting as indicated",
    "Backwall has the inconsistent colour": "Wall needs repainting as indicated",

    # 25: Frame finish
    "Frame finish is scratched as indicated": "Frame finish scratched as indicated",
    "Door frame finish has scratches": "Frame finish scratched as indicated",
    "Frame paint is scratched as indicated": "Frame finish scratched as indicated",
    "Paint on the frame is scratched as indicated": "Frame finish scratched as indicated",
    "Door frame has chipped paint": "Frame finish chipped",
    "Frame is chipped as indicated": "Frame finish chipped",
    "Frame and coating are chipped": "Frame finish chipped",
    "Frame has paint smudges": "Frame finish has paint marks",
    "Frame has paint marks": "Frame finish has paint marks",
    "Frame has paint droplets": "Frame finish has paint marks",

    # 26: Door finish
    "Door finish is chipped as indicated": "Door finish chipped as indicated",
    "Door finish has scratches": "Door finish scratched",
    "Scratches on door exterior": "Door finish scratched",
    "Door finish is scratched": "Door finish scratched",
    "Scratches on door finish": "Door finish scratched",
    "Door finish has paint smudges": "Door finish has paint marks",
    "Door finish has dents on its exterior surface": "Dents on door finish",
    "Finish is damaged": "Door finish damaged as indicated",
    "Damaged finish as indicated": "Door finish damaged as indicated",
    "D2a finish is chipped": "Door finish chipped as indicated",
    "Door stained at bottom": "Door finish damaged as indicated",
    "Stains on exterior surface, paint stains on interior surface": "Door finish damaged as indicated",

    # 27: Door noise
    "Door makes a sound when being opened": "Door squeaks when opening",
    "Door makes loud clipping noise by hinges every time it closes": "Hinge noise when door closes",
    "Hinges are making noise when door is being opened": "Hinge noise when door opens",
    "Window makes a squeak when being opened": "Window squeaks when opening",
    "W1a makes a squeak when being opened": "Window squeaks when opening",

    # 28: Door scratches frame/floor
    "Door scratches against the frame": "Door scratches against frame",
    "Door is scratching against the frame": "Door scratches against frame",
    "Door scratches against the frame when being closed": "Door scratches against frame",
    "Rubs against the frame when closing": "Door scratches against frame",
    "Door does not close, hits against the frame": "Door scratches against frame",
    "Door scratches against the floor": "Door scratches against floor",
    "Door flushes directly with the floor and does not reach door stop": "Door scratches against floor",

    # 29: Door not closing/locking
    "Door cannot fully turn, therefore cannot lock the door": "Door does not close properly",
    "Door does not lock into striker plate": "Lockset does not engage striker plate",
    "Lockset does not click into striker plate": "Lockset does not engage striker plate",
    "Lockset cylinder and thumb turn stuck": "Lockset cylinder stuck",
    "Bathroom lock gets stuck when being closed or opened": "Bathroom lock stuck",
    "Bathroom lock does not lock": "Bathroom lock not functioning",
    "Bathroom lock does not fully turn when trying to lock the door": "Bathroom lock not functioning",
    "D3 magnetic door is not strong enough": "Magnetic door catch too weak",
    "D3 difficult to open, needs force": "Door difficult to open",
    "Window is difficult to close": "Window difficult to close",

    # 30: Dents on door
    "Dents on door, uneven paint and paint stains on interior": "Dents on door as indicated",
    "Dents on door and stains on interior": "Dents on door as indicated",
    "Dents by lockset edges on both sides of door": "Dents on door as indicated",
    "Dent by door handle": "Dents on door as indicated",
    "Dent under W4": "Dents on door as indicated",
    "Dents on wall under floating shelf": "Dents on wall as indicated",

    # 31: Hinges misaligned
    "Hinges installed causing door not to be flushed": "Hinges misaligned, door not flush",
    "Upside of door not flushed at all": "Top of door not flush",
    "Not flushed to wall": "Not flush with wall",

    # 32: Hinges rusty
    "Hinges look water damaged": "Hinges rusted/water damaged",
    "Hinges are rusting as indicated": "Hinges rusted/water damaged",
    "Window hinge is rusting": "Hinges rusted/water damaged",
    "Rusted hinges on sink pack": "Hinges rusted/water damaged",
    "Corners are rusting": "Hinges rusted/water damaged",
    "Hinges need to be repainted": "Hinges rusted/water damaged",

    # 33: Hinges loose
    "Hinges on left lockable pack are loose": "Hinge screws loose",
    "Left door hinge is loose": "Hinge screws loose",
    "B.I.C. right leaf has no hinge at the bottom": "B.I.C. hinge missing",

    # 34: Counter seating
    "Leg support is loose": "Counter seating leg support loose",
    "Counter seating leg support not quite stable": "Counter seating leg support loose",
    "Counter seating loose to floor": "Counter seating leg support loose",
    "Leg support not fixed to floor": "Counter seating leg support loose",
    "Counter seating top is scratched as indicated": "Counter seating top scratched",
    "Counter seating not legibly fixed to wall": "Counter seating not securely fixed to wall",

    # 35: Study desk
    "Study desk missing 1 screw to wall": "Study desk missing screw to wall",
    "Study desk loose screws to wall as indicated": "Study desk missing screw to wall",
    "Screws below the study desk are loose": "Study desk missing screw to wall",
    "One screw missing, one screw hanging loose at study table": "Study desk missing screw to wall",
    "Study desk finish is scratched as indicated": "Study desk finish scratched",
    "Study desk finish has a scratch as indicated": "Study desk finish scratched",
    "Study desk has a crack against the wall": "Study desk cracked at wall",
    "Study desk does not look levelled": "Study desk not level",
    "Study desk light has a screw that is not all the way in": "Study desk light: screw loose",

    # 36: Plaster
    "Plaster recess is chipped above the door": "Plaster damaged as indicated",
    "Plastered recess above door chipped finish": "Plaster damaged as indicated",
    "Plaster recess cracked": "Plaster damaged as indicated",
    "Plaster is not smooth near the door frame": "Plaster damaged as indicated",
    "Plaster is not smooth above the mirror": "Plaster damaged as indicated",
    "Plaster damaged near WIFI cable entry point": "Plaster damaged as indicated",
    "Plaster against the wall is cracking": "Plaster damaged as indicated",
    "Poor plaster work above window": "Plaster damaged as indicated",
    "Bad plaster work around window": "Plaster damaged as indicated",
    "Damaged plaster above the window": "Plaster damaged as indicated",
    "Cracked plaster by panel heater": "Plaster damaged as indicated",
    "Chipped plaster": "Plaster damaged as indicated",
    "Cracked and chipped wall by panel heater plug": "Plaster damaged as indicated",
    "There is a scratch on the plaster as indicated": "Plaster damaged as indicated",
    "Hole in the plaster as indicated": "Plaster damaged as indicated",
    "Chipped wall by single switch on wall": "Plaster damaged as indicated",
    "Chipped wall above door": "Plaster damaged as indicated",
    "Chipped under window and by light switch": "Plaster damaged as indicated",
    "The paint and plaster recess are damaged": "Plaster damaged as indicated",

    # 37: Shadow line recess
    "Shadow line recess at ceiling is not consistent": "Shadow line recess inconsistent",
    "Plaster recess at ceiling is not consistent": "Shadow line recess inconsistent",
    "Gaps in plaster recess at ceiling": "Shadow line recess inconsistent",

    # 38: Gasket
    "Gaskets have gaps with window frame": "Gasket gaps at window frame",
    "Gasket leaves gaps with window frame": "Gasket gaps at window frame",
    "Gap between frame and gasket": "Gasket gaps at window frame",
    "Gasket has gaps on the edges": "Gasket gaps at window frame",

    # 39: Window sill
    "Window sill is not flat": "Window sill not flat",
    "Sill is not flat": "Window sill not flat",
    "Tile into windowsill is not flat": "Window sill not flat",
    "Tile into window sill is missing grout": "Window sill tile: missing grout",
    "Tile into window sill has a large gap to window": "Window sill tile: gap to window",
    "Tile into window sill does not align with tile trim": "Window sill tile: misaligned with trim",
    "Tiles into window sill are not levelled": "Window sill tile: not level",
    "Tiles are not properly aligned with tile trim on the shower step": "Tiles misaligned with tile trim",

    # 40: Window/coating
    "Window coating is damaged as indicated": "Window coating damaged",
    "Window coating is chipped": "Window coating damaged",
    "Coating is damaged": "Window coating damaged",
    "The coating is damaged as indicated": "Window coating damaged",
    "Frame and coating need to be cleaned": "Window coating needs cleaning",
    "Tile trim into window reveal is dirty": "Window reveal needs cleaning",

    # 41: Stove wiring
    "Stove wiring inside to be secured well": "Stove wiring not secured",
    "Stove wire needs to be secured well": "Stove wiring not secured",
    "Lockable pack 1 and 2 need to secure stove wiring": "Stove wiring not secured",

    # 42: Carcass cleaning
    "B.I.C. carcass needs to be cleaned": "Carcass needs cleaning",
    "Residue inside of cupboard": "Carcass needs cleaning",
    "Broom cupboard carcass needs to be cleaned": "Carcass needs cleaning",
    "Lockable pack 1 and 2 carcass needs to be cleaned": "Carcass needs cleaning",
    "Sink pack carcass needs to be cleaned and is chipped": "Carcass needs cleaning",
    "Top of cupboard needs to be cleaned": "Carcass needs cleaning",
    "Bin drawer carcass needs to be cleaned": "Carcass needs cleaning",
    "Needs to be cleaned inside": "Carcass needs cleaning",
    "Needs to be cleaned": "Carcass needs cleaning",

    # 43: Carcass damaged
    "Carcass has mould and chipped": "Carcass has mould",
    "Sink pack carcass has mould": "Carcass has mould",
    "Backwall has mould growth": "Carcass has mould",
    "Carcass is chipped": "Carcass chipped as indicated",
    "Carcass damaged as indicated": "Carcass chipped as indicated",
    "Eye level pack carcass damaged as indicated": "Carcass chipped as indicated",
    "Broom cupboard is chipped as indicated": "Carcass chipped as indicated",
    "Hole inside pack, with chipped part of wood": "Carcass chipped as indicated",
    "Chipped inside same pack": "Carcass chipped as indicated",
    "Cracks inside the pack": "Carcass chipped as indicated",
    "Carcass has water": "Carcass has water damage",
    "Carcass is missing screw covers": "Carcass missing screw covers",

    # 44: Bin drawer
    "Bin drawer runners have sand": "Bin drawer runners stiff",
    "Bin drawer runners get stuck when opening": "Bin drawer runners stiff",
    "Bin drawer hard to push and pull": "Bin drawer runners stiff",

    # 45: Handle
    "Handle does not swing well": "Handle not springing back",
    "Handle does not kick back to place": "Handle not springing back",
    "Handle has no screws to door": "Handle screws missing",
    "Handles are missing screw covers": "Handle screw covers missing",
    "Plastic packaging is still on handle": "Packaging still on handle",
    "Handle of the window needs to be cleaned": "Handle needs cleaning",
    "Residence lock needs to be cleaned": "Handle needs cleaning",
    "Residence lock handle plate has a loose screw": "Handle plate screw loose",

    # 46: Shelf
    "Shelf not installed/fitted in properly": "Shelf not fitted properly",
    "Shelf is water damaged": "Shelf water damaged",
    "Shelf not stable": "Shelf not fitted properly",
    "Floating shelf finish has a crack as indicated": "Floating shelf cracked",
    "Uneven finish by floating shelf": "Floating shelf finish uneven",

    # 47: Soft joint
    "Soft joint is damaged as indicated": "Soft joint damaged as indicated",
    "Soft joint has bubbles": "Soft joint damaged as indicated",
    "Soft joint application is not consistent": "Soft joint damaged as indicated",

    # 48: Fixing to wall
    "Fixing to wall not done well": "Fixing to wall not to standard",
    "Fixing to wall is not to standard": "Fixing to wall not to standard",
    "Not fixed legibly to wall as indicated": "Fixing to wall not to standard",
    "Not well finished to underside": "Fixing to wall not to standard",

    # 49: Loose screws
    "X1 screw hanging loose": "Loose screw as indicated",
    "There is a screw hanging": "Loose screw as indicated",
    "The screw is loose": "Loose screw as indicated",
    "Loose screws as indicated": "Loose screw as indicated",
    "Loose hanging screw by right window": "Loose screw as indicated",
    "Has a screw that is not properly screwed in": "Loose screw as indicated",
    "One screw is missing": "Screw missing as indicated",
    "No screw covers": "Screw covers missing",
    "Striker plate is loose": "Striker plate loose",
    "No strike plate installed": "Striker plate not installed",
    "Ceiling has a screw": "Exposed screw in ceiling",
    "B2B SS pull handle has missing screw": "Pull handle: screw missing",

    # 50: Cleaning
    "Window frame needs to be cleaned": "Window frame needs cleaning",
    "Airbrick finish is dirty": "Airbrick needs cleaning",
    "WC has sand inside": "WC needs cleaning",
    "Mosaic tiles have plaster and paint splashes": "Mosaic tiles need cleaning",
    "Mosaic tiles in shower need to be cleaned": "Mosaic tiles need cleaning",
    "Window sill is dirty": "Window sill needs cleaning",
    "Airbrick in the shower is dirty": "Airbrick needs cleaning",
    "Airbrick above door needs to be cleaned": "Airbrick needs cleaning",
    "Burglar bars need to be cleaned": "Burglar bars need cleaning",
    "DB cover needs to be cleaned": "DB cover needs cleaning",
    "Door needs to be cleaned": "Door needs cleaning",
    "Tapes need to be removed in window frame": "Tape to be removed from frame",
    "Tape needs to be removed in frame": "Tape to be removed from frame",

    # 51: Chipped edge
    "Edges are damaged as indicated": "Chipped edge as indicated",
    "Chipped edge at the bottom as indicated": "Chipped edge as indicated",
    "Chipped at the bottom as indicated": "Chipped edge as indicated",
    "Edge on left damaged as indicated": "Chipped edge as indicated",
    "Damaged on top edge as indicated": "Chipped edge as indicated",
    "Damaged edge as indicated": "Chipped edge as indicated",
    "Board is chipped as indicated": "Chipped edge as indicated",
    "Top has scratches": "Chipped edge as indicated",
    "Scratches and dents on edge": "Chipped edge as indicated",
    "Lower drawer handle is chipped as indicated": "Chipped edge as indicated",
    "Finish is chipped at the top": "Chipped edge as indicated",
    "Finish is chipped and has white paint smudges on the inside": "Chipped edge as indicated",
    "Finish has white paint smudges on the outside": "Chipped edge as indicated",
    "Paint on outside is damaged": "Chipped edge as indicated",
    "Paint on outside is chipped as indicated": "Chipped edge as indicated",

    # 52: WC / Plumbing
    "WC shut off valve is not working": "WC shut-off valve not working",
    "WC shut off valve to be tested, does not refill toilet bucket": "WC shut-off valve not working",
    "WC waste pipe is not installed": "WC waste pipe not installed",
    "Waste pipe to be installed, water running out of WC": "WC waste pipe not installed",
    "WC indicator green colour not showing, only white and red": "WC indicator not working",
    "Water is not coming out of the rose": "No water from shower rose",
    "WHB water flows in low pressure": "WHB low water pressure",
    "Cardboard used between WHB and stand to keep balance": "WHB not stable, shimmed with cardboard",
    "Shower airbrick is loose": "Shower airbrick loose",
    "Installation incomplete inside of sink pack": "Sink pack installation incomplete",
    "Damp wall by W1 above towel rail": "Damp wall as indicated",
    "Wet wall inside sink pack": "Wet wall inside sink pack",

    # 53: Sand in hinges/runners
    "There is sand in the runners": "Sand in runners",
    "Runners are filled with dust, stiff operation": "Sand in runners",
    "Stiff operation": "Sand in runners",

    # 54: Tile trim (other)
    "Tile trim at sink splash back does not reach the eye level pack": "Tile trim short at eye level pack",
    "The tile layout is not straight": "Tile layout not straight",
    "Full height tiling all round is not completed": "Full height tiling incomplete",
    "Missing tile behind door": "Tile missing behind door",
    "Tile is missing behind the door": "Tile missing behind door",

    # 55: Misc
    "Rose and its plate are loose": "Rose cover plate loose",
    "Arm is loose and not finished": "Arm cover plate loose",
    "DB is not installed": "DB not installed",
    "Panel heater plug point has a gap above it": "Gap above panel heater plug point",
    "Random screw hole inside 2nd cabinet as indicated": "Unwanted screw hole in cabinet",
    "Ceiling inside the shower is not to standard": "Shower ceiling not to standard",
    "Wall has marks as indicated": "Wall marks as indicated",
    "There are oil marks on the finish": "Oil marks on finish",
    "There are gaps on window reveal as indicated": "Gaps in window reveal",
    "Gap on the bottom left corner of the window": "Gap in window corner",
    "Third cabinet/drawer does not close all the way": "Cabinet drawer does not close fully",
    "Door is splitting at the top": "Door splitting at top",
    "Glass is broken as indicated": "Glass broken as indicated",
    "Sink pack top is chipped as indicated": "Chipped edge as indicated",
}

# Descriptions to DELETE (Wi-Fi repeater = standard exclusion)
DELETE_DESCRIPTIONS = [
    "Wi-Fi repeater not installed",
]


# ============================================================
# MAIN
# ============================================================
def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('--dry-run', '--execute'):
        print("Usage: python3 scripts/defect_cleanup.py --dry-run")
        print("       python3 scripts/defect_cleanup.py --execute")
        sys.exit(1)

    dry_run = sys.argv[1] == '--dry-run'
    mode = "DRY RUN" if dry_run else "EXECUTE"

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    print(f"=== DEFECT DESCRIPTION CLEANUP ({mode}) ===")
    print(f"Timestamp: {now}")
    print(f"Rename mappings: {len(RENAME_MAP)}")
    print(f"Delete descriptions: {len(DELETE_DESCRIPTIONS)}")
    print()

    # --- BEFORE STATE ---
    print("=== BEFORE STATE ===")
    cur.execute("SELECT COUNT(*) FROM defect WHERE status='open' AND tenant_id=?", (TENANT,))
    before_defects = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT original_comment) FROM defect WHERE status='open' AND tenant_id=?", (TENANT,))
    before_unique = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM defect_library WHERE tenant_id=?", (TENANT,))
    before_library = cur.fetchone()[0]
    print(f"Open defects: {before_defects}")
    print(f"Unique descriptions: {before_unique}")
    print(f"Library entries: {before_library}")
    print()

    # --- PHASE 1: RENAME defect.original_comment ---
    print("=== PHASE 1: RENAME defect.original_comment ===")
    defect_rename_count = 0
    for old_desc, new_desc in RENAME_MAP.items():
        cur.execute(
            "SELECT COUNT(*) FROM defect WHERE original_comment=? AND tenant_id=? AND status='open'",
            (old_desc, TENANT)
        )
        count = cur.fetchone()[0]
        if count > 0:
            print(f"  [{count:3d}x] '{old_desc}' -> '{new_desc}'")
            if not dry_run:
                cur.execute(
                    "UPDATE defect SET original_comment=?, updated_at=? WHERE original_comment=? AND tenant_id=? AND status='open'",
                    (new_desc, now, old_desc, TENANT)
                )
            defect_rename_count += count
    print(f"Defects renamed: {defect_rename_count}")
    print()

    # --- PHASE 2: RENAME inspection_item.comment ---
    print("=== PHASE 2: RENAME inspection_item.comment ===")
    item_rename_count = 0
    for old_desc, new_desc in RENAME_MAP.items():
        cur.execute("""
            SELECT COUNT(*) FROM inspection_item ii
            JOIN inspection i ON ii.inspection_id = i.id
            WHERE ii.comment=? AND i.tenant_id=?
        """, (old_desc, TENANT))
        count = cur.fetchone()[0]
        if count > 0:
            print(f"  [{count:3d}x] '{old_desc}' -> '{new_desc}'")
            if not dry_run:
                cur.execute("""
                    UPDATE inspection_item SET comment=?
                    WHERE comment=? AND inspection_id IN (
                        SELECT id FROM inspection WHERE tenant_id=?
                    )
                """, (new_desc, old_desc, TENANT))
            item_rename_count += count
    print(f"Inspection items renamed: {item_rename_count}")
    print()

    # --- PHASE 3: RENAME defect_library.description ---
    print("=== PHASE 3: RENAME defect_library.description ===")
    lib_rename_count = 0
    for old_desc, new_desc in RENAME_MAP.items():
        cur.execute(
            "SELECT COUNT(*) FROM defect_library WHERE description=? AND tenant_id=?",
            (old_desc, TENANT)
        )
        count = cur.fetchone()[0]
        if count > 0:
            print(f"  [{count:3d}x] '{old_desc}' -> '{new_desc}'")
            if not dry_run:
                cur.execute(
                    "UPDATE defect_library SET description=? WHERE description=? AND tenant_id=?",
                    (new_desc, old_desc, TENANT)
                )
            lib_rename_count += count
    print(f"Library entries renamed: {lib_rename_count}")
    print()

    # --- PHASE 4: DEDUPLICATE defect_library ---
    # After renaming, multiple library entries may have the same description + item_template_id
    print("=== PHASE 4: DEDUPLICATE defect_library ===")
    cur.execute("""
        SELECT description, item_template_id, COUNT(*) as cnt, SUM(usage_count) as total_usage
        FROM defect_library
        WHERE tenant_id=?
        GROUP BY description, item_template_id
        HAVING COUNT(*) > 1
    """, (TENANT,))
    dupes = [dict(r) for r in cur.fetchall()]
    dedup_count = 0
    for d in dupes:
        tmpl = d['item_template_id']
        desc = d['description']
        total_usage = d['total_usage']
        print(f"  Dedup: '{desc}' (template={tmpl}) - {d['cnt']} entries, merging usage_count={total_usage}")
        if not dry_run:
            # Keep the first entry, delete the rest
            if tmpl:
                cur.execute("""
                    SELECT id FROM defect_library
                    WHERE description=? AND item_template_id=? AND tenant_id=?
                    ORDER BY created_at ASC LIMIT 1
                """, (desc, tmpl, TENANT))
            else:
                cur.execute("""
                    SELECT id FROM defect_library
                    WHERE description=? AND item_template_id IS NULL AND tenant_id=?
                    ORDER BY created_at ASC LIMIT 1
                """, (desc, TENANT))
            keep_id = cur.fetchone()[0]
            # Update usage count on the keeper
            cur.execute(
                "UPDATE defect_library SET usage_count=? WHERE id=?",
                (total_usage, keep_id)
            )
            # Delete the rest
            if tmpl:
                cur.execute("""
                    DELETE FROM defect_library
                    WHERE description=? AND item_template_id=? AND tenant_id=? AND id != ?
                """, (desc, tmpl, TENANT, keep_id))
            else:
                cur.execute("""
                    DELETE FROM defect_library
                    WHERE description=? AND item_template_id IS NULL AND tenant_id=? AND id != ?
                """, (desc, TENANT, keep_id))
            dedup_count += cur.rowcount
    print(f"Duplicate library entries removed: {dedup_count}")
    print()

    # --- PHASE 5: DELETE Wi-Fi defects ---
    print("=== PHASE 5: DELETE Wi-Fi repeater defects ===")
    for desc in DELETE_DESCRIPTIONS:
        # Count defects
        cur.execute(
            "SELECT COUNT(*) FROM defect WHERE original_comment=? AND tenant_id=?",
            (desc, TENANT)
        )
        d_count = cur.fetchone()[0]
        print(f"  Defects to delete: {d_count} ('{desc}')")

        if not dry_run and d_count > 0:
            # Delete defect_history first (foreign key)
            cur.execute("""
                DELETE FROM defect_history WHERE defect_id IN (
                    SELECT id FROM defect WHERE original_comment=? AND tenant_id=?
                )
            """, (desc, TENANT))
            print(f"  Defect history deleted: {cur.rowcount}")

            # Delete defects
            cur.execute(
                "DELETE FROM defect WHERE original_comment=? AND tenant_id=?",
                (desc, TENANT)
            )
            print(f"  Defects deleted: {cur.rowcount}")

        # Reset inspection items to skipped (these are exclusion items)
        cur.execute("""
            SELECT COUNT(*) FROM inspection_item ii
            JOIN inspection i ON ii.inspection_id = i.id
            WHERE ii.comment=? AND i.tenant_id=?
        """, (desc, TENANT))
        ii_count = cur.fetchone()[0]
        print(f"  Inspection items to reset: {ii_count}")

        if not dry_run and ii_count > 0:
            cur.execute("""
                UPDATE inspection_item SET status='skipped', comment=NULL
                WHERE comment=? AND inspection_id IN (
                    SELECT id FROM inspection WHERE tenant_id=?
                )
            """, (desc, TENANT))
            print(f"  Inspection items reset to skipped: {cur.rowcount}")

        # Delete library entry
        cur.execute(
            "SELECT COUNT(*) FROM defect_library WHERE description=? AND tenant_id=?",
            (desc, TENANT)
        )
        lib_count = cur.fetchone()[0]
        print(f"  Library entries to delete: {lib_count}")
        if not dry_run and lib_count > 0:
            cur.execute(
                "DELETE FROM defect_library WHERE description=? AND tenant_id=?",
                (desc, TENANT)
            )
            print(f"  Library entries deleted: {cur.rowcount}")
    print()

    # --- COMMIT OR SKIP ---
    if dry_run:
        print("=== DRY RUN COMPLETE - NO CHANGES MADE ===")
        conn.close()
        return

    conn.commit()
    print("=== COMMITTED ===")

    # --- AFTER STATE ---
    print()
    print("=== AFTER STATE ===")
    cur.execute("SELECT COUNT(*) FROM defect WHERE status='open' AND tenant_id=?", (TENANT,))
    after_defects = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT original_comment) FROM defect WHERE status='open' AND tenant_id=?", (TENANT,))
    after_unique = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM defect_library WHERE tenant_id=?", (TENANT,))
    after_library = cur.fetchone()[0]

    print(f"Open defects: {before_defects} -> {after_defects} (delta: {after_defects - before_defects})")
    print(f"Unique descriptions: {before_unique} -> {after_unique} (delta: {after_unique - before_unique})")
    print(f"Library entries: {before_library} -> {after_library} (delta: {after_library - before_library})")
    print()

    # --- VERIFICATION ---
    print("=== VERIFICATION ===")
    # Check no old descriptions remain
    stale_count = 0
    for old_desc in RENAME_MAP.keys():
        cur.execute(
            "SELECT COUNT(*) FROM defect WHERE original_comment=? AND tenant_id=? AND status='open'",
            (old_desc, TENANT)
        )
        c = cur.fetchone()[0]
        if c > 0:
            print(f"  WARNING: '{old_desc}' still has {c} records!")
            stale_count += c
    for desc in DELETE_DESCRIPTIONS:
        cur.execute(
            "SELECT COUNT(*) FROM defect WHERE original_comment=? AND tenant_id=?",
            (desc, TENANT)
        )
        c = cur.fetchone()[0]
        if c > 0:
            print(f"  WARNING: '{desc}' still has {c} records!")
            stale_count += c

    if stale_count == 0:
        print("  All old descriptions cleared successfully")
    else:
        print(f"  WARNING: {stale_count} stale records remain!")

    # Block counts should still match
    cur.execute("SELECT COUNT(*) FROM defect WHERE status='open' AND raised_cycle_id='792812c7'", ())
    b5 = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM defect WHERE status='open' AND raised_cycle_id='36e85327'", ())
    b6 = cur.fetchone()[0]
    print(f"  Block 5 defects: {b5} (was 336, expected ~{336 - sum(1 for d in DELETE_DESCRIPTIONS)})")
    print(f"  Block 6 defects: {b6} (was 525, expected ~{525})")
    print(f"  Total: {b5 + b6}")
    print()
    print("=== CLEANUP COMPLETE ===")

    conn.close()


if __name__ == '__main__':
    main()
