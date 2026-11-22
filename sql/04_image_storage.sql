-- =============================================================================
-- 04_image_storage.sql — Path-Based ImageData vs BLOB Comparison (Q4)
-- =============================================================================
-- Design Rationale:
--   Path-based storage (ImageData.img_path) keeps the RDBMS lightweight, avoids
--   buffer-pool bloat and slow mysqldump backups, and allows direct file/HTTP/CDN
--   serving. Trade-off: requires synchronizing DB rows with filesystem files.
--   Alternative imagedata_blob is shown below for architectural comparison only.

USE warehouse_fleet;

CREATE TABLE IF NOT EXISTS ImageData (
    img_id    INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id  VARCHAR(10)  NOT NULL,
    img_path  VARCHAR(255) NOT NULL,
    timestamp DATETIME     NOT NULL,
    CONSTRAINT fk_imagedata_robot
        FOREIGN KEY (robot_id) REFERENCES Robot(robot_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    INDEX idx_robot_time (robot_id, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Comparison schema: storing raw binary BLOBs directly in MySQL
CREATE TABLE IF NOT EXISTS imagedata_blob (
    img_id     INT         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id   VARCHAR(10) NOT NULL,
    image_data LONGBLOB    NOT NULL,
    timestamp  DATETIME    NOT NULL,
    INDEX idx_blob_robot_time (robot_id, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO ImageData (img_id, robot_id, img_path, timestamp) VALUES
    (1, 'R1', 'data/images/qr_zone_a1.png',     '2025-09-01 08:00:00'),
    (2, 'R2', 'data/images/qr_zone_b2.png',     '2025-09-01 08:30:00'),
    (3, 'R1', 'data/images/cam_r1_pick_01.png', '2025-09-01 08:02:00'),
    (4, 'R2', 'data/images/cam_r2_scan_01.png', '2025-09-01 08:12:00');

-- Retrieve inspection image paths for a robot chronologically
SELECT img_id, robot_id, img_path, timestamp
FROM ImageData
WHERE robot_id = 'R2'
ORDER BY timestamp ASC;
