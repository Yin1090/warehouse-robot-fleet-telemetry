-- =============================================================================
-- 08_preset_dashboard_queries.sql — 5 Core + Extended Dashboard Queries
-- =============================================================================

USE warehouse_fleet;

-- [Preset 1] Robot & attached sensor count
SELECT r.robot_id,
       r.name,
       r.type,
       r.year,
       COUNT(s.sensor_id) AS sensor_count
FROM Robot r
LEFT JOIN Sensor s ON r.robot_id = s.robot_id
GROUP BY r.robot_id, r.name, r.type, r.year
ORDER BY r.robot_id ASC;

-- [Preset 2] Latest measurement value per sensor
SELECT sensor_id, type, robot_id, timestamp, value
FROM (
    SELECT s.sensor_id,
           s.type,
           s.robot_id,
           d.timestamp,
           d.value,
           ROW_NUMBER() OVER (
               PARTITION BY s.sensor_id
               ORDER BY d.timestamp DESC, d.log_id DESC
           ) AS rn
    FROM Sensor s
    LEFT JOIN DataLog d ON s.sensor_id = d.sensor_id
) ranked
WHERE rn = 1
ORDER BY sensor_id ASC;

-- [Preset 3] Temp logs of robot R1 on target date (2025-09-01)
SELECT d.log_id,
       d.robot_id,
       s.sensor_id,
       s.type,
       d.timestamp,
       d.value
FROM DataLog d
JOIN Sensor s ON d.sensor_id = s.sensor_id
WHERE d.robot_id = 'R1'
  AND s.type = 'Temp'
  AND DATE(d.timestamp) = '2025-09-01'
ORDER BY d.timestamp ASC;

-- [Preset 4] Sensors / readings with NULL value
SELECT s.sensor_id,
       s.type,
       s.robot_id,
       d.log_id,
       d.timestamp,
       d.value
FROM Sensor s
LEFT JOIN DataLog d ON s.sensor_id = d.sensor_id
WHERE d.value IS NULL OR s.value IS NULL
ORDER BY s.sensor_id ASC, d.timestamp ASC;

-- [Preset 5] Total DataLog count per robot
SELECT r.robot_id,
       r.name,
       COUNT(d.log_id) AS total_logs
FROM Robot r
LEFT JOIN DataLog d ON r.robot_id = d.robot_id
GROUP BY r.robot_id, r.name
ORDER BY total_logs DESC, r.robot_id ASC;

-- [Extended 6] Performance DENSE_RANK leaderboard
SELECT robot_id,
       COUNT(*) AS task_count,
       ROUND(AVG(TIMESTAMPDIFF(SECOND, start_time, end_time)), 4) AS avg_task_time_s,
       ROUND(AVG(TIMESTAMPDIFF(SECOND, start_time, end_time)) / 60.0, 4) AS avg_task_time_min,
       DENSE_RANK() OVER (
           ORDER BY AVG(TIMESTAMPDIFF(SECOND, start_time, end_time)) ASC
       ) AS perf_rank
FROM Performance
GROUP BY robot_id
ORDER BY perf_rank ASC, robot_id ASC;

-- [Extended 7] Inter-robot command audit log
SELECT cmd_id, sender_id, receiver_id, cmd_content, timestamp
FROM RobotCommand
ORDER BY timestamp DESC, cmd_id DESC;

-- [Extended 8] Normalized 3NF RouteLog trace for R1
SELECT rl.log_id, rl.robot_id, r.name AS robot_name, o.name AS operator_name, rl.location, rl.timestamp
FROM RouteLog rl
JOIN Robot r ON rl.robot_id = r.robot_id
JOIN Operator o ON rl.op_id = o.op_id
WHERE rl.robot_id = 'R1'
ORDER BY rl.timestamp ASC;
