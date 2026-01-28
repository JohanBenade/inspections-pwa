-- Inspections Template - COMPACT TEST VERSION
-- Unit Type: 4-Bed
-- 3 Areas, ~35 items total for easy manual testing

-- =============================================
-- AREAS (3 total)
-- =============================================
INSERT INTO area_template (id, tenant_id, unit_type, area_name, area_order) VALUES 
    ('area-kitchen', 'MONOGRAPH', '4-Bed', 'KITCHEN', 1),
    ('area-bathroom', 'MONOGRAPH', '4-Bed', 'BATHROOM', 2),
    ('area-bedroom', 'MONOGRAPH', '4-Bed', 'BEDROOM', 3);

-- =============================================
-- CATEGORIES
-- =============================================
-- Kitchen: Doors, Plumbing, Electrical
INSERT INTO category_template (id, tenant_id, area_id, category_name, category_order) VALUES 
    ('cat-k-doors', 'MONOGRAPH', 'area-kitchen', 'DOORS', 1),
    ('cat-k-plumbing', 'MONOGRAPH', 'area-kitchen', 'PLUMBING', 2),
    ('cat-k-electrical', 'MONOGRAPH', 'area-kitchen', 'ELECTRICAL', 3);

-- Bathroom: Doors, Plumbing, Finishes
INSERT INTO category_template (id, tenant_id, area_id, category_name, category_order) VALUES 
    ('cat-b-doors', 'MONOGRAPH', 'area-bathroom', 'DOORS', 1),
    ('cat-b-plumbing', 'MONOGRAPH', 'area-bathroom', 'PLUMBING', 2),
    ('cat-b-finishes', 'MONOGRAPH', 'area-bathroom', 'FINISHES', 3);

-- Bedroom: Doors, Windows, Joinery
INSERT INTO category_template (id, tenant_id, area_id, category_name, category_order) VALUES 
    ('cat-r-doors', 'MONOGRAPH', 'area-bedroom', 'DOORS', 1),
    ('cat-r-windows', 'MONOGRAPH', 'area-bedroom', 'WINDOWS', 2),
    ('cat-r-joinery', 'MONOGRAPH', 'area-bedroom', 'JOINERY', 3);

-- =============================================
-- ITEMS - KITCHEN
-- =============================================
-- Kitchen > Doors (parent: D1 with children)
INSERT INTO item_template (id, tenant_id, category_id, parent_item_id, item_description, item_order, depth) VALUES 
    ('k-d1', 'MONOGRAPH', 'cat-k-doors', NULL, 'D1 - Main Entry', 1, 0),
    ('k-d1-frame', 'MONOGRAPH', 'cat-k-doors', 'k-d1', 'frame', 2, 1),
    ('k-d1-leaf', 'MONOGRAPH', 'cat-k-doors', 'k-d1', 'leaf & finish', 3, 1),
    ('k-d1-hinges', 'MONOGRAPH', 'cat-k-doors', 'k-d1', 'hinges', 4, 1),
    ('k-d1-handle', 'MONOGRAPH', 'cat-k-doors', 'k-d1', 'handle & lock', 5, 1);

-- Kitchen > Plumbing (mix of parent and standalone)
INSERT INTO item_template (id, tenant_id, category_id, parent_item_id, item_description, item_order, depth) VALUES 
    ('k-sink', 'MONOGRAPH', 'cat-k-plumbing', NULL, 'Sink', 1, 0),
    ('k-sink-bowl', 'MONOGRAPH', 'cat-k-plumbing', 'k-sink', 'bowl & finish', 2, 1),
    ('k-sink-taps', 'MONOGRAPH', 'cat-k-plumbing', 'k-sink', 'taps', 3, 1),
    ('k-sink-drain', 'MONOGRAPH', 'cat-k-plumbing', 'k-sink', 'drain & trap', 4, 1),
    ('k-geyser', 'MONOGRAPH', 'cat-k-plumbing', NULL, 'Geyser', 5, 0),
    ('k-geyser-unit', 'MONOGRAPH', 'cat-k-plumbing', 'k-geyser', 'unit & insulation', 6, 1),
    ('k-geyser-pipes', 'MONOGRAPH', 'cat-k-plumbing', 'k-geyser', 'pipes & valves', 7, 1);

-- Kitchen > Electrical (standalone items)
INSERT INTO item_template (id, tenant_id, category_id, parent_item_id, item_description, item_order, depth) VALUES 
    ('k-light', 'MONOGRAPH', 'cat-k-electrical', NULL, 'Ceiling light', 1, 0),
    ('k-plug1', 'MONOGRAPH', 'cat-k-electrical', NULL, 'Wall plug - counter', 2, 0),
    ('k-plug2', 'MONOGRAPH', 'cat-k-electrical', NULL, 'Wall plug - stove', 3, 0),
    ('k-switch', 'MONOGRAPH', 'cat-k-electrical', NULL, 'Light switch', 4, 0);

-- =============================================
-- ITEMS - BATHROOM
-- =============================================
-- Bathroom > Doors (parent with children)
INSERT INTO item_template (id, tenant_id, category_id, parent_item_id, item_description, item_order, depth) VALUES 
    ('b-d1', 'MONOGRAPH', 'cat-b-doors', NULL, 'D1 - Bathroom Entry', 1, 0),
    ('b-d1-frame', 'MONOGRAPH', 'cat-b-doors', 'b-d1', 'frame', 2, 1),
    ('b-d1-leaf', 'MONOGRAPH', 'cat-b-doors', 'b-d1', 'leaf & finish', 3, 1),
    ('b-d1-handle', 'MONOGRAPH', 'cat-b-doors', 'b-d1', 'handle & lock', 4, 1);

-- Bathroom > Plumbing (multiple parents)
INSERT INTO item_template (id, tenant_id, category_id, parent_item_id, item_description, item_order, depth) VALUES 
    ('b-toilet', 'MONOGRAPH', 'cat-b-plumbing', NULL, 'Toilet', 1, 0),
    ('b-toilet-pan', 'MONOGRAPH', 'cat-b-plumbing', 'b-toilet', 'pan & seat', 2, 1),
    ('b-toilet-cistern', 'MONOGRAPH', 'cat-b-plumbing', 'b-toilet', 'cistern & flush', 3, 1),
    ('b-shower', 'MONOGRAPH', 'cat-b-plumbing', NULL, 'Shower', 4, 0),
    ('b-shower-head', 'MONOGRAPH', 'cat-b-plumbing', 'b-shower', 'head & arm', 5, 1),
    ('b-shower-mixer', 'MONOGRAPH', 'cat-b-plumbing', 'b-shower', 'mixer valve', 6, 1),
    ('b-shower-drain', 'MONOGRAPH', 'cat-b-plumbing', 'b-shower', 'drain', 7, 1),
    ('b-basin', 'MONOGRAPH', 'cat-b-plumbing', NULL, 'Basin', 8, 0),
    ('b-basin-bowl', 'MONOGRAPH', 'cat-b-plumbing', 'b-basin', 'bowl', 9, 1),
    ('b-basin-taps', 'MONOGRAPH', 'cat-b-plumbing', 'b-basin', 'taps', 10, 1);

-- Bathroom > Finishes (standalone)
INSERT INTO item_template (id, tenant_id, category_id, parent_item_id, item_description, item_order, depth) VALUES 
    ('b-tiles-floor', 'MONOGRAPH', 'cat-b-finishes', NULL, 'Floor tiles', 1, 0),
    ('b-tiles-wall', 'MONOGRAPH', 'cat-b-finishes', NULL, 'Wall tiles', 2, 0),
    ('b-mirror', 'MONOGRAPH', 'cat-b-finishes', NULL, 'Mirror', 3, 0),
    ('b-towelrail', 'MONOGRAPH', 'cat-b-finishes', NULL, 'Towel rail', 4, 0);

-- =============================================
-- ITEMS - BEDROOM
-- =============================================
-- Bedroom > Doors
INSERT INTO item_template (id, tenant_id, category_id, parent_item_id, item_description, item_order, depth) VALUES 
    ('r-d1', 'MONOGRAPH', 'cat-r-doors', NULL, 'D1 - Bedroom Entry', 1, 0),
    ('r-d1-frame', 'MONOGRAPH', 'cat-r-doors', 'r-d1', 'frame', 2, 1),
    ('r-d1-leaf', 'MONOGRAPH', 'cat-r-doors', 'r-d1', 'leaf & finish', 3, 1),
    ('r-d1-handle', 'MONOGRAPH', 'cat-r-doors', 'r-d1', 'handle & lock', 4, 1);

-- Bedroom > Windows (parent with children)
INSERT INTO item_template (id, tenant_id, category_id, parent_item_id, item_description, item_order, depth) VALUES 
    ('r-w1', 'MONOGRAPH', 'cat-r-windows', NULL, 'W1 - Main Window', 1, 0),
    ('r-w1-frame', 'MONOGRAPH', 'cat-r-windows', 'r-w1', 'frame & coating', 2, 1),
    ('r-w1-glass', 'MONOGRAPH', 'cat-r-windows', 'r-w1', 'glass', 3, 1),
    ('r-w1-hinges', 'MONOGRAPH', 'cat-r-windows', 'r-w1', 'hinges', 4, 1),
    ('r-w1-handle', 'MONOGRAPH', 'cat-r-windows', 'r-w1', 'handle', 5, 1),
    ('r-w1-burglar', 'MONOGRAPH', 'cat-r-windows', 'r-w1', 'burglar bars', 6, 1);

-- Bedroom > Joinery (parent: BIC with children)
INSERT INTO item_template (id, tenant_id, category_id, parent_item_id, item_description, item_order, depth) VALUES 
    ('r-bic', 'MONOGRAPH', 'cat-r-joinery', NULL, 'B.I.C. (Built-in Cupboard)', 1, 0),
    ('r-bic-carcass', 'MONOGRAPH', 'cat-r-joinery', 'r-bic', 'carcass', 2, 1),
    ('r-bic-doors', 'MONOGRAPH', 'cat-r-joinery', 'r-bic', 'doors & finish', 3, 1),
    ('r-bic-hinges', 'MONOGRAPH', 'cat-r-joinery', 'r-bic', 'hinges', 4, 1),
    ('r-bic-handles', 'MONOGRAPH', 'cat-r-joinery', 'r-bic', 'handles', 5, 1),
    ('r-bic-shelves', 'MONOGRAPH', 'cat-r-joinery', 'r-bic', 'shelves & rail', 6, 1);

-- =============================================
-- SUMMARY
-- Areas: 3 (Kitchen, Bathroom, Bedroom)
-- Categories: 9
-- Items: 52 total (16 parents, 36 children/standalone)
-- =============================================
