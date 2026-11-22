-- =============================================================================
-- 05_performance_analytics.sql — Task Performance & DENSE_RANK Analytics (Q5)
-- =============================================================================

USE warehouse_fleet;

CREATE TABLE IF NOT EXISTS Performance (
    perf_id    BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id   VARCHAR(10)  NOT NULL,
    task       VARCHAR(100) NOT NULL,
    start_time DATETIME     NOT NULL,
    end_time   DATETIME     NOT NULL,
    CONSTRAINT fk_perf_robot
        FOREIGN KEY (robot_id) REFERENCES Robot(robot_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    INDEX idx_performance_robot_time (robot_id, start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Minimal 180s vs 600s demo seed (R1 fastest: 180.0000 s; R2: 600.0000 s)
INSERT IGNORE INTO Performance (perf_id, robot_id, task, start_time, end_time) VALUES
    (1, 'R1', 'Pick Item', '2025-09-01 08:00:00', '2025-09-01 08:03:00'),
    (2, 'R1', 'Drop Item', '2025-09-01 08:05:00', '2025-09-01 08:08:00'),
    (3, 'R2', 'Scan Zone', '2025-09-01 08:10:00', '2025-09-01 08:20:00');

-- 1. Per-task duration in seconds
SELECT robot_id,
       task,
       start_time,
       end_time,
       TIMESTAMPDIFF(SECOND, start_time, end_time) AS duration_sec
FROM Performance
ORDER BY start_time ASC;

-- 2. Average task duration per robot (seconds & minutes) + DENSE_RANK
SELECT robot_id,
       COUNT(*) AS task_count,
       ROUND(AVG(TIMESTAMPDIFF(SECOND, start_time, end_time)), 4) AS avg_duration_sec,
       ROUND(AVG(TIMESTAMPDIFF(SECOND, start_time, end_time)) / 60.0, 4) AS avg_task_time_min,
       DENSE_RANK() OVER (
           ORDER BY AVG(TIMESTAMPDIFF(SECOND, start_time, end_time)) ASC
       ) AS perf_rank
FROM Performance
GROUP BY robot_id
ORDER BY perf_rank ASC, robot_id ASC;

-- 3. Fastest robot(s) on target date (ties share rnk = 1)
SELECT robot_id, avg_duration_sec
FROM (
    SELECT robot_id,
           AVG(TIMESTAMPDIFF(SECOND, start_time, end_time)) AS avg_duration_sec,
           DENSE_RANK() OVER (
               ORDER BY AVG(TIMESTAMPDIFF(SECOND, start_time, end_time)) ASC
           ) AS rnk
    FROM Performance
    WHERE start_time >= '2025-09-01 00:00:00'
      AND start_time <  '2025-09-02 00:00:00'
    GROUP BY robot_id
) ranked
WHERE rnk = 1;
