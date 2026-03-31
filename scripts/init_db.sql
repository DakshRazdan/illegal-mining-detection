-- scripts/init_db.sql
-- PostGIS schema initialization for Illegal Mining Detection System
-- Runs automatically via docker-entrypoint-initdb.d

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- ============================================================
-- Table: lease_boundaries
-- Mining lease polygons from government records
-- ============================================================
CREATE TABLE IF NOT EXISTS lease_boundaries (
    id              SERIAL PRIMARY KEY,
    lease_id        VARCHAR(64) UNIQUE NOT NULL,
    mine_name       VARCHAR(256),
    company         VARCHAR(256),
    commodity       VARCHAR(64),
    status          VARCHAR(32),    -- ACTIVE | EXPIRED | SUSPENDED
    ec_id           VARCHAR(64),
    area_ha         FLOAT,
    district        VARCHAR(128),
    state           VARCHAR(64)     DEFAULT 'Jharkhand',
    granted_year    INTEGER,
    expires_year    INTEGER,
    geom            GEOMETRY(POLYGON, 4326),
    created_at      TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lease_geom ON lease_boundaries USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_lease_status ON lease_boundaries (status);

-- ============================================================
-- Table: detections
-- Raw detection outputs from ML pipeline
-- ============================================================
CREATE TABLE IF NOT EXISTS detections (
    id              SERIAL PRIMARY KEY,
    detection_id    VARCHAR(64) UNIQUE NOT NULL,
    lon             FLOAT NOT NULL,
    lat             FLOAT NOT NULL,
    area_ha         FLOAT,
    mining_score    FLOAT,
    method          VARCHAR(32),    -- spectral_rf | unet | yolo | ensemble | synthetic
    detected_at     TIMESTAMPTZ     DEFAULT NOW(),
    run_id          VARCHAR(64),
    geom            GEOMETRY(POINT, 4326),
    extra           JSONB
);

CREATE INDEX IF NOT EXISTS idx_detection_geom ON detections USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_detection_run ON detections (run_id);

-- ============================================================
-- Table: verification_results
-- Output from the verification / legal check layer
-- ============================================================
CREATE TABLE IF NOT EXISTS verification_results (
    id              SERIAL PRIMARY KEY,
    detection_id    VARCHAR(64) REFERENCES detections(detection_id),
    lease_status    VARCHAR(32),
    lease_id        VARCHAR(64),
    lease_company   VARCHAR(256),
    ec_valid        BOOLEAN,
    ec_id           VARCHAR(64),
    land_type       VARCHAR(64),
    risk_score      FLOAT,
    risk_level      VARCHAR(16),    -- CRITICAL | HIGH | MEDIUM | LOW
    is_illegal      BOOLEAN,
    verified_at     TIMESTAMPTZ     DEFAULT NOW(),
    notes           TEXT[]
);

CREATE INDEX IF NOT EXISTS idx_verify_detection ON verification_results (detection_id);
CREATE INDEX IF NOT EXISTS idx_verify_risk ON verification_results (risk_level);
CREATE INDEX IF NOT EXISTS idx_verify_illegal ON verification_results (is_illegal);

-- ============================================================
-- Table: alert_records
-- Dispatched alerts log
-- ============================================================
CREATE TABLE IF NOT EXISTS alert_records (
    id                  SERIAL PRIMARY KEY,
    alert_id            VARCHAR(64) UNIQUE NOT NULL,
    detection_id        VARCHAR(64) REFERENCES detections(detection_id),
    risk_level          VARCHAR(16),
    lon                 FLOAT,
    lat                 FLOAT,
    area_ha             FLOAT,
    lease_status        VARCHAR(32),
    risk_score          FLOAT,
    message             TEXT,
    whatsapp_status     VARCHAR(16) DEFAULT 'PENDING',
    sms_status          VARCHAR(16) DEFAULT 'PENDING',
    dispatched_at       TIMESTAMPTZ,
    district            VARCHAR(128),
    state               VARCHAR(64) DEFAULT 'Jharkhand',
    geom                GEOMETRY(POINT, 4326),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_geom ON alert_records USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_alert_risk ON alert_records (risk_level);
CREATE INDEX IF NOT EXISTS idx_alert_status ON alert_records (whatsapp_status);

-- ============================================================
-- View: illegal_hotspots
-- Pre-joined view for dashboard consumption
-- ============================================================
CREATE OR REPLACE VIEW illegal_hotspots AS
SELECT
    d.detection_id,
    d.lon,
    d.lat,
    d.area_ha,
    d.mining_score,
    d.method,
    d.detected_at,
    v.lease_status,
    v.lease_id,
    v.lease_company,
    v.ec_valid,
    v.risk_score,
    v.risk_level,
    v.is_illegal,
    a.alert_id,
    a.whatsapp_status,
    a.dispatched_at,
    d.geom
FROM detections d
LEFT JOIN verification_results v ON d.detection_id = v.detection_id
LEFT JOIN alert_records a ON d.detection_id = a.detection_id
WHERE v.is_illegal = TRUE
ORDER BY v.risk_score DESC;
