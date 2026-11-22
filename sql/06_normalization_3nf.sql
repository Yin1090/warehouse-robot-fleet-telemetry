-- =============================================================================
-- 06_normalization_3nf.sql — 2NF/3NF Decomposition of RobotRoute_raw (Q6)
-- =============================================================================
-- Anomaly Analysis on RobotRoute_raw(robot_id, robot_name, location, operator, timestamp):
--   - Update anomaly: renaming AlphaBot requires scanning/updating hundreds of route rows.
--   - Insert anomaly: cannot register a new robot or operator without inventing a route event.
--   - Delete anomaly: purging old route logs for a robot erases its identity metadata.
-- Decomposition to 3NF separates Robot, Operator, and RouteLog via foreign keys.

USE warehouse_fleet;

CREATE TABLE IF NOT EXISTS Robot (
    robot_id VARCHAR(10) NOT NULL PRIMARY KEY,
    name     VARCHAR(50) NOT NULL,
    type     VARCHAR(30) NULL DEFAULT 'AGV',
    year     INT         NULL DEFAULT 2024
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Operator (
    op_id INT         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name  VARCHAR(50) NOT NULL,
    shift VARCHAR(20) NULL DEFAULT 'Day'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS RouteLog (
    log_id    BIGINT      NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id  VARCHAR(10) NOT NULL,
    op_id     INT         NOT NULL,
    location  VARCHAR(50) NOT NULL,
    timestamp DATETIME    NOT NULL,
    CONSTRAINT fk_routelog_robot
        FOREIGN KEY (robot_id) REFERENCES Robot(robot_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_routelog_operator
        FOREIGN KEY (op_id) REFERENCES Operator(op_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    INDEX idx_route_robot_time (robot_id, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Inspect RouteLog.op_id column metadata (used by seed_routelog_r1_safe)
SELECT DATA_TYPE, COLUMN_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'RouteLog'
  AND COLUMN_NAME = 'op_id';
