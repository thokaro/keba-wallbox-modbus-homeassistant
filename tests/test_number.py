"""Tests for KEBA number entities."""

from __future__ import annotations

import asyncio

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.keba_wallbox_modbus import number as number_module
from custom_components.keba_wallbox_modbus.number import KebaNumberEntity
from custom_components.keba_wallbox_modbus.profiles import P30_PROFILE
from custom_components.keba_wallbox_modbus.registers import (
    KEY_FAILSAFE_CURRENT,
    KEY_MAX_CHARGING_CURRENT,
    KEY_MAX_SUPPORTED_CURRENT,
    KEY_VOLTAGE_L1,
    KEY_VOLTAGE_L2,
    KEY_VOLTAGE_L3,
    WRITE_REGISTER_CHARGING_CURRENT,
    WRITE_REGISTER_FAILSAFE_CURRENT,
)
from custom_components.keba_wallbox_modbus.write_descriptions import NUMBER_DESCRIPTIONS


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
    """Minimal coordinator for number entity write tests."""

    def __init__(self) -> None:
        self.hass = FakeHass()
        self.data = {
            KEY_MAX_SUPPORTED_CURRENT: 16_000,
            KEY_VOLTAGE_L1: 226,
            KEY_VOLTAGE_L2: 225,
            KEY_VOLTAGE_L3: 225,
        }
        self.model_key = P30_PROFILE.model_key
        self.profile = P30_PROFILE
        self.charging_power_target = None
        self.charging_current_regulation_enabled = False
        self.writes = []
        self.apply_power_targets = []
        self.refresh_count = 0
        self.targeted_refreshes = []
        self.assumed_values = []

    def set_charging_power_target(self, value):
        """Record the charging power target."""
        self.charging_power_target = None if value is None or value <= 0 else value

    def set_charging_current_regulation_enabled(self, enabled):
        """Record whether current regulation is enabled."""
        self.charging_current_regulation_enabled = enabled

    async def async_write_register(self, address, value):
        """Record a register write."""
        self.writes.append((address, value))

    async def async_apply_charging_power_target(
        self,
        value,
        *,
        assume_readback=False,
        refresh_readback=False,
        refresh_delay=0,
        background_refresh=False,
        refresh_name=None,
    ):
        """Record one direct charging power application."""
        self.apply_power_targets.append(value)
        applied = await self.async_write_register_and_refresh(
            WRITE_REGISTER_CHARGING_CURRENT,
            7500,
            assume_values=(
                {KEY_MAX_CHARGING_CURRENT: 7500} if assume_readback else None
            ),
            refresh=refresh_readback,
            refresh_keys=(KEY_MAX_CHARGING_CURRENT,),
            refresh_delay=refresh_delay,
            background_refresh=background_refresh,
            refresh_name=refresh_name,
        )
        return 7500 if applied else None

    async def async_apply_charging_current_regulation(self):
        """Pretend to apply regulation."""

    async def async_request_refresh(self):
        """Pretend to refresh data."""
        self.refresh_count += 1

    async def async_refresh_register_keys(self, keys):
        """Record a targeted register refresh."""
        self.targeted_refreshes.append(tuple(keys))

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
        """Record a write and emulate coordinator follow-up behavior."""
        self.writes.append((address, value))
        if assume_values is not None:
            self.assume_register_values(assume_values)

        if refresh:
            target = (
                self.async_request_refresh()
                if refresh_keys is None
                else self.async_refresh_register_keys(refresh_keys)
            )
            if background_refresh:
                self.hass.async_create_task(target, name=refresh_name)
            else:
                await target

        return True

    def assume_register_values(self, values):
        """Record optimistic register data."""
        self.assumed_values.append(dict(values))
        self.data.update(values)


def _number_description(key: str):
    return next(
        description for description in NUMBER_DESCRIPTIONS if description.key == key
    )


def _number_entity(key: str, coordinator: FakeCoordinator) -> KebaNumberEntity:
    entity = KebaNumberEntity.__new__(KebaNumberEntity)
    entity.coordinator = coordinator
    entity.entity_description = _number_description(key)
    entity._cached_native_value = None
    entity._restored_native_value = None
    entity.async_write_ha_state = lambda: None
    return entity


@pytest.fixture(autouse=True)
def fast_readback_delay(monkeypatch) -> None:
    """Avoid waiting for the production readback delay in entity tests."""
    monkeypatch.setattr(number_module, "WRITE_READBACK_DELAY", 0)


async def test_charging_power_write_updates_regulation_target_without_switch() -> None:
    """Charging power writes the target current even while regulation is off."""
    coordinator = FakeCoordinator()
    entity = _number_entity("charging_power", coordinator)

    await entity.async_set_native_value(7.0)

    assert coordinator.charging_power_target == 7.0
    assert coordinator.apply_power_targets == [7.0]
    assert coordinator.writes == [(WRITE_REGISTER_CHARGING_CURRENT, 7500)]
    assert coordinator.assumed_values == [{KEY_MAX_CHARGING_CURRENT: 7500}]
    assert coordinator.data[KEY_MAX_CHARGING_CURRENT] == 7500
    await asyncio.gather(*coordinator.hass.tasks)
    assert coordinator.refresh_count == 0
    assert coordinator.targeted_refreshes == [(KEY_MAX_CHARGING_CURRENT,)]


async def test_charging_power_write_applies_target_with_regulation_enabled() -> None:
    """Charging power writes one target current before follow-up regulation."""
    coordinator = FakeCoordinator()
    coordinator.charging_current_regulation_enabled = True
    entity = _number_entity("charging_power", coordinator)

    await entity.async_set_native_value(7.0)

    assert coordinator.charging_power_target == 7.0
    assert coordinator.apply_power_targets == [7.0]
    assert coordinator.writes == [(WRITE_REGISTER_CHARGING_CURRENT, 7500)]
    assert coordinator.assumed_values == [{KEY_MAX_CHARGING_CURRENT: 7500}]
    assert coordinator.data[KEY_MAX_CHARGING_CURRENT] == 7500
    await asyncio.gather(*coordinator.hass.tasks)
    assert coordinator.refresh_count == 0
    assert coordinator.targeted_refreshes == [(KEY_MAX_CHARGING_CURRENT,)]


async def test_charging_current_write_disables_regulation() -> None:
    """Direct current writes remain a manual override."""
    coordinator = FakeCoordinator()
    coordinator.charging_current_regulation_enabled = True
    entity = _number_entity("charging_current_limit", coordinator)

    await entity.async_set_native_value(10.1)

    assert not coordinator.charging_current_regulation_enabled
    assert coordinator.writes == [(WRITE_REGISTER_CHARGING_CURRENT, 10100)]
    assert coordinator.assumed_values == [{KEY_MAX_CHARGING_CURRENT: 10100}]
    assert coordinator.data[KEY_MAX_CHARGING_CURRENT] == 10100
    await asyncio.gather(*coordinator.hass.tasks)
    assert coordinator.refresh_count == 0
    assert coordinator.targeted_refreshes == [(KEY_MAX_CHARGING_CURRENT,)]


async def test_charging_current_write_rejects_non_tenth_amp_step() -> None:
    """Direct current writes must stay aligned to tenth amp steps."""
    coordinator = FakeCoordinator()
    coordinator.charging_current_regulation_enabled = True
    entity = _number_entity("charging_current_limit", coordinator)

    with pytest.raises(HomeAssistantError, match="0.1 A steps"):
        await entity.async_set_native_value(10.25)

    assert coordinator.charging_current_regulation_enabled
    assert coordinator.writes == []
    assert coordinator.assumed_values == []
    assert coordinator.hass.tasks == []


async def test_failsafe_current_write_accepts_tenth_amp_step() -> None:
    """Failsafe current can be written in tenth amp steps."""
    coordinator = FakeCoordinator()
    entity = _number_entity("failsafe_current", coordinator)

    await entity.async_set_native_value(6.6)

    assert coordinator.writes == [(WRITE_REGISTER_FAILSAFE_CURRENT, 6600)]
    assert coordinator.assumed_values == [{KEY_FAILSAFE_CURRENT: 6600}]
    assert coordinator.data[KEY_FAILSAFE_CURRENT] == 6600
    await asyncio.gather(*coordinator.hass.tasks)
    assert coordinator.refresh_count == 0
    assert coordinator.targeted_refreshes == [(KEY_FAILSAFE_CURRENT,)]
