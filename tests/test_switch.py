"""Tests for KEBA switch entities."""

from __future__ import annotations

import asyncio

from custom_components.keba_wallbox_modbus.registers import WRITE_REGISTER_CHARGER_ENABLE
from custom_components.keba_wallbox_modbus.switch import (
    KebaChargerEnableSwitch,
    KebaChargingCurrentRegulationSwitch,
)


class FakeHass:
    """Minimal hass task scheduler for background refresh tests."""

    def __init__(self) -> None:
        self.tasks = []

    def async_create_task(self, target, name=None):
        """Schedule a background task."""
        task = asyncio.create_task(target, name=name)
        self.tasks.append(task)
        return task


class FakeCoordinator:
    """Minimal coordinator for switch entity write tests."""

    def __init__(self) -> None:
        self.hass = FakeHass()
        self.charging_current_regulation_enabled = False
        self.apply_count = 0
        self.refresh_count = 0
        self.writes = []

    def set_charging_current_regulation_enabled(self, enabled):
        """Record whether current regulation is enabled."""
        self.charging_current_regulation_enabled = enabled

    async def async_write_register(self, address, value):
        """Record a register write."""
        self.writes.append((address, value))

    async def async_write_register_and_refresh(
        self,
        address,
        value,
        *,
        refresh_keys=None,
        assume_values=None,
        refresh=True,
        refresh_delay=0,
        background_refresh=False,
        refresh_name=None,
    ):
        """Record a register write with central refresh behavior."""
        self.writes.append((address, value))
        if refresh:
            target = self.async_request_refresh()
            if background_refresh:
                self.hass.async_create_task(target, name=refresh_name)
            else:
                await target
        return True

    async def async_apply_charging_current_regulation(self):
        """Record that regulation was applied."""
        self.apply_count += 1

    async def async_request_refresh(self):
        """Record that data was refreshed."""
        self.refresh_count += 1


def _regulation_switch(
    coordinator: FakeCoordinator,
) -> KebaChargingCurrentRegulationSwitch:
    entity = KebaChargingCurrentRegulationSwitch.__new__(
        KebaChargingCurrentRegulationSwitch
    )
    entity.coordinator = coordinator
    entity.async_write_ha_state = lambda: None
    return entity


def _enable_switch(coordinator: FakeCoordinator) -> KebaChargerEnableSwitch:
    entity = KebaChargerEnableSwitch.__new__(KebaChargerEnableSwitch)
    entity.coordinator = coordinator
    entity._is_on = None
    entity.async_write_ha_state = lambda: None
    return entity


async def test_charging_current_regulation_switch_enables_regulation() -> None:
    """Turning on the switch enables and immediately applies regulation."""
    coordinator = FakeCoordinator()
    entity = _regulation_switch(coordinator)

    await entity.async_turn_on()

    assert coordinator.charging_current_regulation_enabled
    assert entity.is_on
    assert coordinator.apply_count == 1
    await asyncio.gather(*coordinator.hass.tasks)
    assert coordinator.refresh_count == 1


async def test_charging_current_regulation_switch_disables_regulation() -> None:
    """Turning off the switch leaves the current limit untouched and refreshes."""
    coordinator = FakeCoordinator()
    coordinator.charging_current_regulation_enabled = True
    entity = _regulation_switch(coordinator)

    await entity.async_turn_off()

    assert not coordinator.charging_current_regulation_enabled
    assert not entity.is_on
    assert coordinator.apply_count == 0
    await asyncio.gather(*coordinator.hass.tasks)
    assert coordinator.refresh_count == 1


async def test_charger_enable_switch_writes_without_waiting_for_refresh() -> None:
    """Turning on the charger writes the register and schedules a refresh."""
    coordinator = FakeCoordinator()
    entity = _enable_switch(coordinator)

    await entity.async_turn_on()

    assert entity.is_on
    assert coordinator.writes == [(WRITE_REGISTER_CHARGER_ENABLE, 1)]
    await asyncio.gather(*coordinator.hass.tasks)
    assert coordinator.refresh_count == 1


async def test_charger_disable_switch_writes_without_waiting_for_refresh() -> None:
    """Turning off the charger writes the register and schedules a refresh."""
    coordinator = FakeCoordinator()
    entity = _enable_switch(coordinator)

    await entity.async_turn_off()

    assert entity.is_on is False
    assert coordinator.writes == [(WRITE_REGISTER_CHARGER_ENABLE, 0)]
    await asyncio.gather(*coordinator.hass.tasks)
    assert coordinator.refresh_count == 1
