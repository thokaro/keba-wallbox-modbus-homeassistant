"""Register keys and maps for KEBA wallboxes."""

from __future__ import annotations

KEY_CHARGING_STATE = "charging_state"
KEY_CABLE_STATE = "cable_state"
KEY_ERROR_CODE = "error_code"
KEY_CURRENT_L1 = "current_l1"
KEY_CURRENT_L2 = "current_l2"
KEY_CURRENT_L3 = "current_l3"
KEY_SERIAL_NUMBER = "serial_number"
KEY_PRODUCT = "product"
KEY_FIRMWARE_VERSION = "firmware_version"
KEY_ACTIVE_POWER = "active_power"
KEY_TOTAL_ENERGY = "total_energy"
KEY_VOLTAGE_L1 = "voltage_l1"
KEY_VOLTAGE_L2 = "voltage_l2"
KEY_VOLTAGE_L3 = "voltage_l3"
KEY_POWER_FACTOR = "power_factor"
KEY_MAX_CHARGING_CURRENT = "max_charging_current"
KEY_MAX_SUPPORTED_CURRENT = "max_supported_current"
KEY_FAST_CHARGING_STATE = "fast_charging_state"
KEY_SESSION_ENERGY = "session_energy"
KEY_PHASE_SWITCH_SOURCE = "phase_switch_source"
KEY_PHASE_SWITCH_STATE = "phase_switch_state"
KEY_FAILSAFE_CURRENT = "failsafe_current"
KEY_FAILSAFE_TIMEOUT = "failsafe_timeout"
KEY_HARDWARE_REVISION_DEVICE = "hardware_revision_device"
KEY_HARDWARE_REVISION_MS10 = "hardware_revision_ms10"

DISCOVERY_REGISTER_MAP: dict[str, int] = {
    KEY_SERIAL_NUMBER: 1014,
    KEY_PRODUCT: 1016,
    KEY_FIRMWARE_VERSION: 1018,
}

COMMON_RUNTIME_REGISTER_MAP: dict[str, int] = {
    KEY_CHARGING_STATE: 1000,
    KEY_CABLE_STATE: 1004,
    KEY_ERROR_CODE: 1006,
    KEY_CURRENT_L1: 1008,
    KEY_CURRENT_L2: 1010,
    KEY_CURRENT_L3: 1012,
    KEY_ACTIVE_POWER: 1020,
    KEY_TOTAL_ENERGY: 1036,
    KEY_VOLTAGE_L1: 1040,
    KEY_VOLTAGE_L2: 1042,
    KEY_VOLTAGE_L3: 1044,
    KEY_POWER_FACTOR: 1046,
    KEY_MAX_CHARGING_CURRENT: 1100,
    KEY_MAX_SUPPORTED_CURRENT: 1110,
    KEY_SESSION_ENERGY: 1502,
    KEY_PHASE_SWITCH_SOURCE: 1550,
    KEY_PHASE_SWITCH_STATE: 1552,
    KEY_FAILSAFE_CURRENT: 1600,
    KEY_FAILSAFE_TIMEOUT: 1602,
}

COMMON_OPTIONAL_RUNTIME_KEYS = frozenset(
    {
        KEY_VOLTAGE_L1,
        KEY_VOLTAGE_L2,
        KEY_VOLTAGE_L3,
        KEY_POWER_FACTOR,
        KEY_PHASE_SWITCH_SOURCE,
        KEY_PHASE_SWITCH_STATE,
        KEY_FAILSAFE_CURRENT,
        KEY_FAILSAFE_TIMEOUT,
    }
)

P30_STATIC_REGISTER_MAP: dict[str, int] = {
    **DISCOVERY_REGISTER_MAP,
}

P40_STATIC_REGISTER_MAP: dict[str, int] = {
    **DISCOVERY_REGISTER_MAP,
    KEY_HARDWARE_REVISION_DEVICE: 1700,
    KEY_HARDWARE_REVISION_MS10: 1702,
}

P30_RUNTIME_REGISTER_MAP: dict[str, int] = {
    **COMMON_RUNTIME_REGISTER_MAP,
}

P40_RUNTIME_REGISTER_MAP: dict[str, int] = {
    **COMMON_RUNTIME_REGISTER_MAP,
    KEY_FAST_CHARGING_STATE: 1200,
}

CHARGING_STATE_MAP: dict[int, str] = {
    0: "start-up",
    1: "not ready",
    2: "ready",
    3: "charging",
    4: "error",
    5: "suspended",
}

CABLE_STATE_MAP: dict[int, str] = {
    0: "not connected",
    1: "plugged into wallbox",
    3: "plugged into wallbox and locked",
    5: "plugged into wallbox and vehicle",
    7: "plugged into wallbox, vehicle and locked",
}

FAST_CHARGING_STATE_MAP: dict[int, str] = {
    0: "inactive",
    1: "active",
}

PHASE_SWITCH_SOURCE_MAP_P30: dict[int, str] = {
    0: "No source",
    1: "OCPP",
    2: "REST API",
    3: "Modbus TCP",
    4: "UDP",
}

PHASE_SWITCH_SOURCE_MAP_P40: dict[int, str] = {
    0: "No source",
    1: "OCPP",
    2: "REST API",
    3: "Modbus TCP",
}

PHASE_SWITCH_STATE_MAP: dict[int, str] = {
    1: "1 phase",
    3: "3 phases",
}

PHASE_SWITCH_STATE_WRITE_MAP: dict[str, int] = {
    "1 phase": 0,
    "3 phases": 1,
}

__all__ = [
    "CABLE_STATE_MAP",
    "CHARGING_STATE_MAP",
    "COMMON_OPTIONAL_RUNTIME_KEYS",
    "COMMON_RUNTIME_REGISTER_MAP",
    "DISCOVERY_REGISTER_MAP",
    "FAST_CHARGING_STATE_MAP",
    "KEY_ACTIVE_POWER",
    "KEY_CABLE_STATE",
    "KEY_CHARGING_STATE",
    "KEY_CURRENT_L1",
    "KEY_CURRENT_L2",
    "KEY_CURRENT_L3",
    "KEY_ERROR_CODE",
    "KEY_FAILSAFE_CURRENT",
    "KEY_FAILSAFE_TIMEOUT",
    "KEY_FAST_CHARGING_STATE",
    "KEY_FIRMWARE_VERSION",
    "KEY_HARDWARE_REVISION_DEVICE",
    "KEY_HARDWARE_REVISION_MS10",
    "KEY_MAX_CHARGING_CURRENT",
    "KEY_MAX_SUPPORTED_CURRENT",
    "KEY_PHASE_SWITCH_SOURCE",
    "KEY_PHASE_SWITCH_STATE",
    "KEY_POWER_FACTOR",
    "KEY_PRODUCT",
    "KEY_SERIAL_NUMBER",
    "KEY_SESSION_ENERGY",
    "KEY_TOTAL_ENERGY",
    "KEY_VOLTAGE_L1",
    "KEY_VOLTAGE_L2",
    "KEY_VOLTAGE_L3",
    "P30_RUNTIME_REGISTER_MAP",
    "P30_STATIC_REGISTER_MAP",
    "P40_RUNTIME_REGISTER_MAP",
    "P40_STATIC_REGISTER_MAP",
    "PHASE_SWITCH_SOURCE_MAP_P30",
    "PHASE_SWITCH_SOURCE_MAP_P40",
    "PHASE_SWITCH_STATE_MAP",
    "PHASE_SWITCH_STATE_WRITE_MAP",
]
