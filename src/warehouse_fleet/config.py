"""Environment-based configuration loaders for database and MQTT settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """Dual-dialect database configuration (SQLite offline default or MySQL 8.0)."""

    dialect: str = "sqlite"
    sqlite_path: str = "warehouse_fleet.db"
    host: str = "localhost"
    port: int = 3306
    user: str = "fleet_user"
    password: str = "CHANGE_ME_DB_PASSWORD"
    database: str = "warehouse_fleet"
    mysql_driver: str = "pymysql"

    @classmethod
    def from_env(cls, env_file: Path | str | None = None) -> DatabaseConfig:
        if env_file is not None:
            load_dotenv(dotenv_path=env_file, override=False)
        else:
            load_dotenv(override=False)

        return cls(
            dialect=os.getenv("DB_DIALECT", "sqlite").strip().lower(),
            sqlite_path=os.getenv("DB_SQLITE_PATH", "warehouse_fleet.db").strip(),
            host=os.getenv("DB_HOST", "localhost").strip(),
            port=int(os.getenv("DB_PORT", "").strip() or "3306"),
            user=os.getenv("DB_USER", "fleet_user").strip(),
            password=os.getenv("DB_PASSWORD", "CHANGE_ME_DB_PASSWORD"),
            database=os.getenv("DB_NAME", "warehouse_fleet").strip(),
            mysql_driver=os.getenv("DB_MYSQL_DRIVER", "pymysql").strip().lower(),
        )

    def sqlalchemy_url(self) -> str:
        if self.dialect == "sqlite":
            if self.sqlite_path == ":memory:":
                return "sqlite:///:memory:"
            resolved = Path(self.sqlite_path).as_posix()
            return f"sqlite:///{resolved}"
        if self.dialect == "mysql":
            user_enc = quote_plus(self.user)
            pass_enc = quote_plus(self.password)
            return (
                f"mysql+{self.mysql_driver}://{user_enc}:{pass_enc}"
                f"@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
            )
        raise ValueError(f"Unsupported DB_DIALECT: {self.dialect!r}")


@dataclass(frozen=True, slots=True)
class MqttConfig:
    """MQTT broker settings for optional live Mosquitto ingestion."""

    broker: str = "localhost"
    port: int = 1883
    username: str = "fleet_mqtt_user"
    password: str = "CHANGE_ME_MQTT_PASSWORD"
    topic: str = "robot/R1/sensor/dht22"
    client_id: str = "SQL_Logger"

    @classmethod
    def from_env(cls, env_file: Path | str | None = None) -> MqttConfig:
        if env_file is not None:
            load_dotenv(dotenv_path=env_file, override=False)
        else:
            load_dotenv(override=False)

        return cls(
            broker=os.getenv("MQTT_BROKER", "localhost").strip(),
            port=int(os.getenv("MQTT_PORT", "").strip() or "1883"),
            username=os.getenv("MQTT_USER", "fleet_mqtt_user").strip(),
            password=os.getenv("MQTT_PASS", "CHANGE_ME_MQTT_PASSWORD"),
            topic=os.getenv("MQTT_TOPIC", "robot/R1/sensor/dht22").strip(),
            client_id=os.getenv("MQTT_CLIENT_ID", "SQL_Logger").strip(),
        )
