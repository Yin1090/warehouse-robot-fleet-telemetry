-- =============================================================================
-- 01_core_erd_schema.sql — Core Warehouse Fleet ERD & Sample Seed (MySQL 8.0)
-- Topic 5 / Question 1: Robot, Sensor, Operator, DataLog
-- =============================================================================

CREATE DATABASE IF NOT EXISTS warehouse_fleet
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE warehouse_fleet;

CREATE TABLE IF NOT EXISTS Robot (
    robot_id VARCHAR(10) NOT NULL PRIMARY KEY,
    name     VARCHAR(50) NOT NULL,
    type     VARCHAR(30) NULL DEFAULT 'AGV',
    year     INT         NULL DEFAULT 2024
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Sensor (
    sensor_id VARCHAR(10)   NOT NULL PRIMARY KEY,
    robot_id  VARCHAR(10)   NOT NULL,
    type      VARCHAR(30)   NOT NULL,
    value     DECIMAL(10,2) NULL,
    timestamp DATETIME      NULL,
    CONSTRAINT fk_sensor_robot
        FOREIGN KEY (robot_id) REFERENCES Robot(robot_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    INDEX idx_sensor_robot (robot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Operator (
    op_id INT         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name  VARCHAR(50) NOT NULL,
    shift VARCHAR(20) NULL DEFAULT 'Day'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS DataLog (
    log_id    BIGINT        NOT NULL AUTO_INCREMENT PRIMARY KEY,
    op_id     INT           NULL,
    robot_id  VARCHAR(10)   NOT NULL,
    sensor_id VARCHAR(10)   NOT NULL,
    timestamp DATETIME      NOT NULL,
    value     DECIMAL(10,2) NULL,
    CONSTRAINT fk_datalog_operator
        FOREIGN KEY (op_id) REFERENCES Operator(op_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,
    CONSTRAINT fk_datalog_robot
        FOREIGN KEY (robot_id) REFERENCES Robot(robot_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_datalog_sensor
        FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    INDEX idx_datalog_robot_time (robot_id, timestamp),
    INDEX idx_datalog_sensor_time (sensor_id, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Verified sample seed (including S1/Temp = 28.50, S2/Camera = NULL, and R4 for benchmarks)
INSERT IGNORE INTO Robot (robot_id, name, type, year) VALUES
    ('R1', 'AlphaBot', 'AGV',   2023),
    ('R2', 'BetaBot',  'Drone', 2024),
    ('R3', 'GammaBot', 'AGV',   2024),
    ('R4', 'DeltaBot', 'AGV',   2024);

INSERT IGNORE INTO Operator (op_id, name, shift) VALUES
    (1, 'Operator A', 'Morning'),
    (2, 'Operator B', 'Night');

INSERT IGNORE INTO Sensor (sensor_id, robot_id, type, value, timestamp) VALUES
    ('S1', 'R1', 'Temp',   28.50, '2025-09-01 08:00:00'),
    ('S2', 'R2', 'Camera', NULL,  '2025-09-01 08:05:00');

INSERT IGNORE INTO DataLog (log_id, op_id, robot_id, sensor_id, timestamp, value) VALUES
    (1, 1, 'R1', 'S1', '2025-09-01 08:00:00', 28.50),
    (2, 2, 'R2', 'S2', '2025-09-01 08:05:00', NULL);
