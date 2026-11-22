-- =============================================================================
-- 02_raw_route_tables.sql — Denormalized Route Logs & Indexed Queries (Q2)
-- =============================================================================

USE warehouse_fleet;

CREATE TABLE IF NOT EXISTS RobotRoute_raw (
    id         BIGINT      NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id   VARCHAR(10) NOT NULL,
    robot_name VARCHAR(50) NOT NULL,
    location   VARCHAR(50) NOT NULL,
    operator   VARCHAR(50) NOT NULL,
    timestamp  DATETIME    NOT NULL,
    INDEX idx_rr_robot_time (robot_id, timestamp),
    INDEX idx_rr_time (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS RobotMoveLog (
    id         BIGINT      NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id   VARCHAR(10) NOT NULL,
    robot_name VARCHAR(50) NOT NULL,
    zone       VARCHAR(50) NOT NULL,
    operator   VARCHAR(50) NOT NULL,
    timestamp  DATETIME    NOT NULL,
    INDEX idx_rml_robot_time (robot_id, timestamp),
    INDEX idx_rml_time (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Daily trajectory query (standard DATE filter)
SELECT robot_id, robot_name, location, operator, timestamp
FROM RobotRoute_raw
WHERE robot_id = 'R1'
  AND DATE(timestamp) = '2025-09-01'
ORDER BY timestamp ASC;

-- Index-friendly half-open range scan on composite idx_rr_robot_time(robot_id, timestamp)
SELECT robot_id, robot_name, location, operator, timestamp
FROM RobotRoute_raw
WHERE robot_id = 'R1'
  AND timestamp >= '2025-09-01 00:00:00'
  AND timestamp <  '2025-09-02 00:00:00'
ORDER BY timestamp ASC;

-- Combined dashboard MoveLog trajectory query
SELECT zone, timestamp
FROM RobotMoveLog
WHERE robot_id = 'RB01'
  AND timestamp >= '2025-10-07 00:00:00'
  AND timestamp <  '2025-10-08 00:00:00'
ORDER BY timestamp ASC;
