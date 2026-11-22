-- =============================================================================
-- 03_robot_commands.sql — Inter-Robot Command Log (Q3)
-- =============================================================================

USE warehouse_fleet;

CREATE TABLE IF NOT EXISTS RobotCommand (
    cmd_id      BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sender_id   VARCHAR(10)  NOT NULL,
    receiver_id VARCHAR(10)  NOT NULL,
    cmd_content VARCHAR(200) NOT NULL,
    timestamp   DATETIME     NOT NULL,
    CONSTRAINT fk_cmd_sender
        FOREIGN KEY (sender_id) REFERENCES Robot(robot_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_cmd_receiver
        FOREIGN KEY (receiver_id) REFERENCES Robot(robot_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    INDEX idx_cmd_pair_time (sender_id, receiver_id, timestamp),
    INDEX idx_cmd_time (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Sample R1 <-> R2 handshake commands
INSERT IGNORE INTO RobotCommand (cmd_id, sender_id, receiver_id, cmd_content, timestamp) VALUES
    (1, 'R1', 'R2', 'Move to A', '2025-09-01 08:00:00'),
    (2, 'R2', 'R1', 'OK',        '2025-09-01 08:01:00');

-- Pairwise command audit query
SELECT cmd_id, sender_id, receiver_id, timestamp, cmd_content
FROM RobotCommand
WHERE sender_id = 'R1'
  AND receiver_id = 'R2'
  AND timestamp >= '2025-09-01 00:00:00'
  AND timestamp <  '2025-09-02 00:00:00'
ORDER BY timestamp ASC;
