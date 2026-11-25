# Warehouse Robot Fleet Telemetry

**Bilingual Documentation / Tài liệu song ngữ (English & Tiếng Việt)**

---

## English

### 1. Overview
**Warehouse Robot Fleet Telemetry** is an end-to-end robotics data engineering, IoT telemetry, and analytics platform designed for multi-robot warehouse fleets. It implements a complete dual-dialect relational architecture (production **MySQL 8.0** DDL/analytics + offline **SQLite / SQLAlchemy 2.x** execution), **3NF** route normalization with schema-polymorphic seeding, **ESP32** (`DHT22` + `VL53L0X`) MQTT firmware, a decoupled `SQL_Logger` ingest pipeline, deterministic datasets and inspection images, and a **6-tab Tkinter** monitoring dashboard.

#### Key Capabilities
1. **Core Fleet ERD (`Robot`, `Sensor`, `Operator`, `DataLog`)**: Enforces referential integrity across robots, sensors, operators, and nullable sensor telemetry (`NULL` camera/offline readings).
2. **Denormalized Route Logs (`RobotRoute_raw`, `RobotMoveLog`)**: 1,000-row deterministic movement dataset (`RobotRoute.csv`) with composite `(robot_id, timestamp)` indexing.
3. **Inter-Robot Commands (`RobotCommand`)**: Pairwise sender/receiver handshake audit logs with `ON UPDATE CASCADE ON DELETE RESTRICT` constraints.
4. **Inspection Image Metadata (`ImageData`)**: Path-based storage (`data/images/*.png`) with traversal-safe path resolution and architectural comparison against `imagedata_blob`.
5. **Performance Analytics (`Performance`)**: Task duration tracking (`TIMESTAMPDIFF` on MySQL / `julianday` on SQLite) and `DENSE_RANK() OVER (ORDER BY AVG(...) ASC)` ranking across both a minimal `180s/600s` demo and a 1,000-row benchmark (`R1=8.4051`, `R4=8.4160`, `R3=8.7714`, `R2=8.7920` min).
6. **3NF Normalization & Safe Seeding (`RouteLog`)**: Decomposes route anomalies into `Robot`, `Operator`, and `RouteLog`, with `seed_routelog_r1_safe` dynamically inspecting `RouteLog.op_id` types (numeric vs string).
7. **ESP32 Firmware & MQTT `SQL_Logger`**: Sanitized Arduino/ESP32 sketch (`DHT22` on `GPIO 27`, `VL53L0X` I2C, 5000 ms cadence) plus a dual-mode Python logger (`paho-mqtt` `MQTTv311` + offline `SimulatedMqttBus`).
8. **6-Tab Tkinter Dashboard & CLI**: MVC-separated `FleetDashboardController` + `WarehouseFleetApp` (`Robots`, `Sensors`, `DataLogs`, `RouteLog / MoveLog`, `Analytics & Queries`, `Image Viewer`) and `warehouse-fleet` CLI.

---

### 2. Architecture & Datasets

```text
warehouse-robot-fleet-telemetry/
├── .env.example                       # Environment template (SQLite default / optional MySQL & MQTT)
├── pyproject.toml                     # Package metadata, optional extras, pytest pythonpath
├── requirements.txt                   # Core offline dependencies
├── sql/                               # Production MySQL 8.0 scripts (01..08)
│   ├── 01_core_erd_schema.sql
│   ├── 02_raw_route_tables.sql
│   ├── 03_robot_commands.sql
│   ├── 04_image_storage.sql
│   ├── 05_performance_analytics.sql
│   ├── 06_normalization_3nf.sql
│   ├── 07_sensor_log_schema.sql
│   └── 08_preset_dashboard_queries.sql
├── firmware/
│   ├── secrets.h.example              # Sanitized Wi-Fi & MQTT credential placeholders
│   └── esp32_dht22_vl53l0x_mqtt.ino   # ESP32 telemetry publisher
├── data/
│   ├── RobotRoute.csv                 # 1,000 rows (R1..R3, Zone A..D, 5*i % 600 min)
│   ├── robot_movelog_sample.csv       # 48 rows (RB01..RB03, Zone A..F)
│   ├── performance_benchmark.csv      # 1,000 rows (250 tasks x 4 robots -> exact DENSE_RANK)
│   ├── sensor_log_sample.csv          # 12 rows (id 415..426, 5s DHT22 cadence)
│   └── images/*.png                   # 4 synthetic QR & warehouse camera inspection PNGs (320x240)
├── src/warehouse_fleet/
│   ├── config.py, db.py, datasets.py
│   ├── queries.py, mqtt_logger.py
│   ├── controller.py, dashboard.py, cli.py
└── tests/                             # Offline pytest suite (schema, queries, datasets, MQTT, UI, CLI, sanitization)
```

---

### 3. Setup & Usage

#### Prerequisites
- Python `>= 3.10` (tested on Python `3.12.10`)
- Core packages: `SQLAlchemy >= 2.0`, `pillow >= 10.0`, `python-dotenv >= 1.0`, `pytest >= 8.0`, standard-library `sqlite3` and `tkinter`
- Optional live integrations: `paho-mqtt`, `pymysql` / `mysql-connector-python`

#### Installation
```bash
pip install -r requirements.txt
pip install -e .
```

*(Optional live broker/MySQL support: `pip install -e ".[all]"`)*

#### CLI Workflows (Offline SQLite Default)
```bash
# 1. Regenerate deterministic CSVs & PNG assets
warehouse-fleet generate-data

# 2. Initialize schema & seed datasets (add --with-benchmark for 1,000-row DENSE_RANK dataset)
warehouse-fleet init-db --with-benchmark

# 3. Seed 25 normalized 3NF RouteLog entries for R1
warehouse-fleet seed-routelog --robot-id R1 --day 2025-09-01

# 4. Run preset analytical queries (1..10)
warehouse-fleet query --preset 6_performance_dense_rank

# 5. Replay simulated ESP32 MQTT telemetry into SensorLog
warehouse-fleet mqtt-logger --simulate

# 6. Launch the 6-tab Tkinter Dashboard
warehouse-fleet dashboard
```

---

### 4. Automated Tests
Run the complete offline test suite (no external MySQL or Mosquitto broker required):

```bash
python -m pytest -q
```

---

## Tiếng Việt

### 1. Tổng quan
**Warehouse Robot Fleet Telemetry** là nền tảng thu thập dữ liệu IoT, chuẩn hóa cơ sở dữ liệu và phân tích hiệu suất cho đội robot kho vận. Dự án hỗ trợ đồng thời hai hệ quản trị (**MySQL 8.0** chuẩn production và **SQLite / SQLAlchemy 2.x** chạy offline), chuẩn hóa dữ liệu **3NF** kèm hàm nạp thông minh kiểm tra kiểu cột, firmware **ESP32** (`DHT22` + `VL53L0X`) gửi **MQTT**, bộ thu nhận `SQL_Logger`, bộ dữ liệu kiểm thử xác định trước và giao diện **Tkinter 6 tab**.

#### Tính năng chính
1. **Mô hình ERD cốt lõi (`Robot`, `Sensor`, `Operator`, `DataLog`)**: Ràng buộc khóa ngoại chặt chẽ, hỗ trợ giá trị cảm biến `NULL` (ví dụ cảm biến `Camera`).
2. **Nhật ký lộ trình thô (`RobotRoute_raw`, `RobotMoveLog`)**: Bộ dữ liệu 1.000 dòng (`RobotRoute.csv`) kèm chỉ mục kết hợp `(robot_id, timestamp)`.
3. **Lệnh giao tiếp giữa robot (`RobotCommand`)**: Ghi nhận lệnh gửi/nhận (`R1 <-> R2`) với ràng buộc `ON UPDATE CASCADE ON DELETE RESTRICT`.
4. **Lưu trữ ảnh kiểm tra (`ImageData`)**: Thiết kế lưu đường dẫn tương đối (`data/images/*.png`) chống path-traversal và đối chiếu kiến trúc với `imagedata_blob`.
5. **Phân tích hiệu suất (`Performance`)**: Tính thời lượng tác vụ (`TIMESTAMPDIFF` trên MySQL / `julianday` trên SQLite) và xếp hạng `DENSE_RANK() OVER (ORDER BY AVG(...) ASC)` khớp cả mẫu `180s/600s` lẫn benchmark 1.000 dòng (`R1=8.4051`, `R4=8.4160`, `R3=8.7714`, `R2=8.7920` phút).
6. **Chuẩn hóa 3NF & Seeder an toàn (`RouteLog`)**: Tách bảng `Robot`, `Operator`, `RouteLog` loại bỏ dị thường cập nhật/thêm/xóa; hàm `seed_routelog_r1_safe` tự động nhận diện kiểu `op_id` (số nguyên hoặc chuỗi).
7. **Firmware ESP32 & MQTT `SQL_Logger`**: Mã nguồn ESP32 (`DHT22` chân `GPIO 27`, `VL53L0X` I2C, chu kỳ `5000 ms`) đã loại bỏ thông tin nhạy cảm, đi kèm logger hỗ trợ cả `paho-mqtt` (`MQTTv311`) lẫn `SimulatedMqttBus` chạy offline.
8. **Dashboard Tkinter 6 tab & CLI**: Tách biệt tầng điều khiển `FleetDashboardController` khỏi giao diện (`Robots`, `Sensors`, `DataLogs`, `RouteLog / MoveLog`, `Analytics & Queries`, `Image Viewer`) và công cụ dòng lệnh `warehouse-fleet`.

---

### 2. Kiến trúc & Dữ liệu
- `sql/01..08.sql`: Toàn bộ script MySQL 8.0 chuẩn cho từng bài toán (ERD, lộ trình thô, lệnh robot, lưu trữ ảnh, hiệu suất `DENSE_RANK`, chuẩn hóa 3NF, `SensorLog`, và 8 truy vấn SQL trong `08_preset_dashboard_queries.sql`; Python `queries.py` cung cấp đủ 10 truy vấn preset).
- `data/RobotRoute.csv`: 1.000 bản ghi di chuyển (`R1..R3`, `Zone A..D`, chu kỳ 5 phút lặp trong cửa sổ 10 giờ).
- `data/robot_movelog_sample.csv`: 48 bản ghi mẫu cho đội `RB01..RB03`.
- `data/performance_benchmark.csv`: 1.000 bản ghi tác vụ (250 tác vụ × 4 robot) tái lập chính xác giá trị trung bình 4 chữ số thập phân.
- `data/sensor_log_sample.csv`: 12 mẫu `DHT22` (`id 415..426`, chu kỳ 5 giây, nhiệt độ `23.40–23.60 °C`, độ ẩm `50.20–51.20 %`).
- `data/images/*.png`: 4 ảnh kiểm tra QR và camera kho hàng tổng hợp bằng Pillow (`320x240`).

---

### 3. Cài đặt & Sử dụng

#### Cài đặt phụ thuộc
```bash
pip install -r requirements.txt
pip install -e .
```

*(Tùy chọn cài thêm driver MySQL & MQTT thật: `pip install -e ".[all]"`)*

#### Chạy nhanh qua CLI (mặc định SQLite offline)
```bash
# Sinh lại dữ liệu CSV và ảnh PNG mẫu
warehouse-fleet generate-data

# Khởi tạo schema & nạp dữ liệu mẫu (thêm --with-benchmark để nạp 1.000 dòng DENSE_RANK)
warehouse-fleet init-db --with-benchmark

# Nạp 25 dòng RouteLog chuẩn 3NF cho robot R1
warehouse-fleet seed-routelog --robot-id R1 --day 2025-09-01

# Chạy truy vấn phân tích mẫu
warehouse-fleet query --preset 6_performance_dense_rank

# Mô phỏng nhận bản tin MQTT từ ESP32 vào bảng SensorLog
warehouse-fleet mqtt-logger --simulate

# Mở giao diện Tkinter 6 tab
warehouse-fleet dashboard
```

---

### 4. Kiểm thử tự động
Chạy toàn bộ bộ kiểm thử `pytest` hoàn toàn offline (không cần MySQL server hay Mosquitto broker):

```bash
python -m pytest -q
```
