-- ============================================
-- INSPECTIONS PWA - DATABASE SCHEMA
-- Version: 2.0
-- Updated: 28 January 2026
-- Stack: Flask + HTMX + SQLite
-- ============================================

-- ============================================
-- REFERENCE DATA
-- ============================================

CREATE TABLE IF NOT EXISTS project (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    project_name TEXT NOT NULL,
    client_name TEXT NOT NULL,
    project_code TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS phase (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    phase_name TEXT NOT NULL,
    phase_code TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES project(id)
);

CREATE TABLE IF NOT EXISTS unit (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    block TEXT,
    floor INTEGER,
    unit_number TEXT NOT NULL,
    unit_type TEXT NOT NULL,
    status TEXT DEFAULT 'not_started',
    -- Values: not_started | in_progress | defects_open | cleared | certified
    FOREIGN KEY (phase_id) REFERENCES phase(id),
    UNIQUE(phase_id, unit_number)
);

CREATE TABLE IF NOT EXISTS area_template (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    unit_type TEXT NOT NULL,
    area_name TEXT NOT NULL,
    area_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS category_template (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    area_id TEXT NOT NULL,
    category_name TEXT NOT NULL,
    category_order INTEGER NOT NULL,
    FOREIGN KEY (area_id) REFERENCES area_template(id)
);

CREATE TABLE IF NOT EXISTS item_template (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    parent_item_id TEXT,
    item_description TEXT NOT NULL,
    item_order INTEGER NOT NULL,
    depth INTEGER DEFAULT 0,
    FOREIGN KEY (category_id) REFERENCES category_template(id)
);

-- ============================================
-- USERS
-- ============================================

CREATE TABLE IF NOT EXISTS inspector (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT,
    role TEXT DEFAULT 'student',
    -- Values: student | architect | admin
    active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- INSPECTION CYCLES
-- Parent record created by architect before inspections
-- ============================================

CREATE TABLE IF NOT EXISTS inspection_cycle (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    cycle_number INTEGER NOT NULL,
    unit_start TEXT,
    unit_end TEXT,
    general_notes TEXT,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active',
    -- Values: active | closed
    FOREIGN KEY (phase_id) REFERENCES phase(id),
    FOREIGN KEY (created_by) REFERENCES inspector(id),
    UNIQUE(phase_id, cycle_number)
);

-- ============================================
-- CYCLE EXCLUDED ITEMS
-- Items/sub-items excluded from this cycle
-- ============================================

CREATE TABLE IF NOT EXISTS cycle_excluded_item (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    item_template_id TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cycle_id) REFERENCES inspection_cycle(id),
    FOREIGN KEY (item_template_id) REFERENCES item_template(id),
    UNIQUE(cycle_id, item_template_id)
);

-- ============================================
-- CYCLE AREA NOTES
-- Notes per area for a cycle (e.g., "Kitchen electrical not installed")
-- ============================================

CREATE TABLE IF NOT EXISTS cycle_area_note (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    area_template_id TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cycle_id) REFERENCES inspection_cycle(id),
    FOREIGN KEY (area_template_id) REFERENCES area_template(id),
    UNIQUE(cycle_id, area_template_id)
);

-- ============================================
-- INSPECTIONS
-- Unit inspection within a cycle
-- ============================================

CREATE TABLE IF NOT EXISTS inspection (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    
    inspection_date DATE NOT NULL,
    inspector_id TEXT NOT NULL,
    inspector_name TEXT NOT NULL,
    
    status TEXT DEFAULT 'in_progress',
    -- Values: in_progress | submitted
    
    submitted_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (unit_id) REFERENCES unit(id),
    FOREIGN KEY (cycle_id) REFERENCES inspection_cycle(id),
    UNIQUE(unit_id, cycle_id)
);

-- ============================================
-- INSPECTION ITEMS
-- Per unit per cycle
-- ============================================

CREATE TABLE IF NOT EXISTS inspection_item (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    inspection_id TEXT NOT NULL,
    item_template_id TEXT NOT NULL,
    
    status TEXT NOT NULL DEFAULT 'pending',
    -- Values: pending | ok | not_to_standard | not_installed | skipped
    -- skipped = excluded at cycle level
    
    comment TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (inspection_id) REFERENCES inspection(id),
    FOREIGN KEY (item_template_id) REFERENCES item_template(id),
    UNIQUE(inspection_id, item_template_id)
);

-- ============================================
-- DEFECTS
-- Lifecycle across cycles
-- ============================================

CREATE TABLE IF NOT EXISTS defect (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    item_template_id TEXT NOT NULL,
    
    raised_cycle_id TEXT NOT NULL,
    defect_type TEXT NOT NULL,
    -- Values: not_to_standard | not_installed
    
    status TEXT DEFAULT 'open',
    -- Values: open | cleared
    
    original_comment TEXT,
    clearance_note TEXT,
    
    cleared_cycle_id TEXT,
    cleared_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (unit_id) REFERENCES unit(id),
    FOREIGN KEY (raised_cycle_id) REFERENCES inspection_cycle(id),
    FOREIGN KEY (cleared_cycle_id) REFERENCES inspection_cycle(id),
    FOREIGN KEY (item_template_id) REFERENCES item_template(id)
);

-- ============================================
-- DEFECT HISTORY
-- Audit trail - comments per cycle
-- ============================================

CREATE TABLE IF NOT EXISTS defect_history (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    defect_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    comment TEXT NOT NULL,
    status TEXT NOT NULL,
    -- Values: open | cleared
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (defect_id) REFERENCES defect(id),
    FOREIGN KEY (cycle_id) REFERENCES inspection_cycle(id)
);

-- ============================================
-- CATEGORY COMMENTS
-- General comments at category level (DOORS, WINDOWS, etc.)
-- ============================================

CREATE TABLE IF NOT EXISTS category_comment (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    category_template_id TEXT NOT NULL,
    
    raised_cycle_id TEXT NOT NULL,
    
    status TEXT DEFAULT 'open',
    -- Values: open | cleared
    
    cleared_cycle_id TEXT,
    cleared_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (unit_id) REFERENCES unit(id),
    FOREIGN KEY (category_template_id) REFERENCES category_template(id),
    FOREIGN KEY (raised_cycle_id) REFERENCES inspection_cycle(id),
    FOREIGN KEY (cleared_cycle_id) REFERENCES inspection_cycle(id)
);

-- ============================================
-- CATEGORY COMMENT HISTORY
-- Audit trail
-- ============================================

CREATE TABLE IF NOT EXISTS category_comment_history (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    category_comment_id TEXT NOT NULL,
    cycle_id TEXT,
    comment TEXT NOT NULL,
    status TEXT NOT NULL,
    -- Values: open | cleared
    updated_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_comment_id) REFERENCES category_comment(id),
    FOREIGN KEY (cycle_id) REFERENCES inspection_cycle(id)
);

-- ============================================
-- SCHEMA VERSION
-- ============================================

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_version (version) VALUES (2);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX IF NOT EXISTS idx_unit_phase ON unit(phase_id);
CREATE INDEX IF NOT EXISTS idx_unit_status ON unit(status);
CREATE INDEX IF NOT EXISTS idx_cycle_phase ON inspection_cycle(phase_id);
CREATE INDEX IF NOT EXISTS idx_cycle_status ON inspection_cycle(status);
CREATE INDEX IF NOT EXISTS idx_inspection_unit ON inspection(unit_id);
CREATE INDEX IF NOT EXISTS idx_inspection_cycle ON inspection(cycle_id);
CREATE INDEX IF NOT EXISTS idx_inspection_status ON inspection(status);
CREATE INDEX IF NOT EXISTS idx_inspection_item_inspection ON inspection_item(inspection_id);
CREATE INDEX IF NOT EXISTS idx_defect_unit ON defect(unit_id);
CREATE INDEX IF NOT EXISTS idx_defect_status ON defect(status);
CREATE INDEX IF NOT EXISTS idx_defect_history_defect ON defect_history(defect_id);
CREATE INDEX IF NOT EXISTS idx_category_comment_unit ON category_comment(unit_id);
CREATE INDEX IF NOT EXISTS idx_excluded_item_cycle ON cycle_excluded_item(cycle_id);
