-- =============================================================================
-- 07_sensor_log_schema.sql — ESP32 DHT22 MQTT Telemetry Table (Q8)
-- =============================================================================

USE warehouse_fleet;

CREATE TABLE IF NOT EXISTS SensorLog (
    id         INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    robot_id   VARCHAR(10)  NOT NULL,
    sensor     VARCHAR(30)  NOT NULL,
    temp_c     DECIMAL(5,2) NOT NULL,
    hum_pct    DECIMAL(5,2) NOT NULL,
    ts_epoch   BIGINT       NOT NULL,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sensorlog_robot_ts (robot_id, ts_epoch),
    INDEX idx_sensorlog_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Latest 20 telemetry frames for robot R1
SELECT id, robot_id, sensor, temp_c, hum_pct, ts_epoch, created_at
FROM SensorLog
WHERE robot_id = 'R1'
ORDER BY ts_epoch DESC, id DESC
LIMIT 20;

-- Aggregated temperature & humidity summary per robot/sensor
SELECT robot_id,
       sensor,
       COUNT(*) AS sample_count,
       ROUND(MIN(temp_c), 2) AS min_temp_c,
       ROUND(AVG(temp_c), 2) AS avg_temp_c,
       ROUND(MAX(temp_c), 2) AS max_temp_c,
       ROUND(AVG(hum_pct), 2) AS avg_hum_pct
FROM SensorLog
GROUP BY robot_id, sensor
ORDER BY robot_id, sensor;
