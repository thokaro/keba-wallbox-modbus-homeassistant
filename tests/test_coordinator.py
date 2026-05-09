"""Tests for KEBA coordinator helper behavior."""

from __future__ import annotations

from custom_components.keba_wallbox_modbus.const import WRITE_REGISTER_CHARGING_CURRENT
from custom_components.keba_wallbox_modbus.coordinator import KebaDataUpdateCoordinator
from custom_components.keba_wallbox_modbus.profiles import P30_PROFILE
from custom_components.keba_wallbox_modbus.registers import (
    KEY_ACTIVE_POWER,
    KEY_MAX_CHARGING_CURRENT,
    KEY_MAX_SUPPORTED_CURRENT,
    KEY_POWER_FACTOR,
    KEY_VOLTAGE_L1,
    KEY_VOLTAGE_L2,
    KEY_VOLTAGE_L3,
)


async def test_charging_power_target_write_skips_next_enabled_regulation() -> None:
    """Changing charging power writes once and avoids immediate stale regulation."""
    coordinator = KebaDataUpdateCoordinator.__new__(KebaDataUpdateCoordinator)
    coordinator.data = None
    coordinator._profile = P30_PROFILE
    coordinator._charging_power_target = 5.0
    coordinator._charging_current_regulation_enabled = True
    coordinator._charging_current_regulation_holdoff_cycles = 0
    writes = []

    async def async_write_register(address: int, value: int) -> None:
        writes.append((address, value))

    coordinator.async_write_register = async_write_register

    assert await coordinator.async_apply_charging_power_target(5.0) == 7_200
    assert writes == [(WRITE_REGISTER_CHARGING_CURRENT, 7_200)]

    data = {
        KEY_ACTIVE_POWER: 4_744_000,
        KEY_MAX_CHARGING_CURRENT: 7_200,
        KEY_MAX_SUPPORTED_CURRENT: 16_000,
        KEY_POWER_FACTOR: 998,
        KEY_VOLTAGE_L1: 226,
        KEY_VOLTAGE_L2: 225,
        KEY_VOLTAGE_L3: 225,
    }

    assert await coordinator.async_apply_charging_current_regulation(data) is None
    assert writes == [(WRITE_REGISTER_CHARGING_CURRENT, 7_200)]
    assert coordinator._charging_current_regulation_holdoff_cycles == 1

    assert await coordinator.async_apply_charging_current_regulation(data) is None
    assert writes == [(WRITE_REGISTER_CHARGING_CURRENT, 7_200)]
    assert coordinator._charging_current_regulation_holdoff_cycles == 0
