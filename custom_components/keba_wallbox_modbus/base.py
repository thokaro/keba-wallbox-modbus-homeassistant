"""Base constants for the KEBA Wallbox Modbus integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "keba_wallbox_modbus"
MANUFACTURER = "KEBA"
MODEL = "KeContact Wallbox"
MODEL_KEY_P30 = "p30"
MODEL_KEY_P40 = "p40"
MODEL_NAME_P30 = "KeContact P30"
MODEL_NAME_P40 = "KeContact P40"

UDP_DISPLAY_PORT = 7090
UDP_DISPLAY_MAX_LENGTH = 23
UDP_DISPLAY_MAX_DURATION = 10

DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 5
DEFAULT_UNIT_ID = 255
DEFAULT_DISPLAY_MIN_TIME = 2
DEFAULT_DISPLAY_MAX_TIME = 10

CONF_DISPLAY_MAX_TIME = "display_max_time"
CONF_DISPLAY_MIN_TIME = "display_min_time"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_UDP_HOST = "udp_host"
CONF_UNIT_ID = "unit_id"
MIN_READ_INTERVAL = 0.6
MIN_WRITE_INTERVAL = 5.0

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.BUTTON,
    Platform.NOTIFY,
]

__all__ = [
    "CONF_DISPLAY_MAX_TIME",
    "CONF_DISPLAY_MIN_TIME",
    "CONF_SCAN_INTERVAL",
    "CONF_TIMEOUT",
    "CONF_UNIT_ID",
    "CONF_UDP_HOST",
    "DEFAULT_DISPLAY_MAX_TIME",
    "DEFAULT_DISPLAY_MIN_TIME",
    "DEFAULT_PORT",
    "DEFAULT_SCAN_INTERVAL",
    "DEFAULT_TIMEOUT",
    "DEFAULT_UNIT_ID",
    "DOMAIN",
    "MANUFACTURER",
    "MIN_READ_INTERVAL",
    "MIN_WRITE_INTERVAL",
    "MODEL",
    "MODEL_KEY_P30",
    "MODEL_KEY_P40",
    "MODEL_NAME_P30",
    "MODEL_NAME_P40",
    "PLATFORMS",
    "UDP_DISPLAY_MAX_DURATION",
    "UDP_DISPLAY_MAX_LENGTH",
    "UDP_DISPLAY_PORT",
]
