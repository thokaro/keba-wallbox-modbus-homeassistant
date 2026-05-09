"""Switch platform for KEBA Wallbox Modbus."""

from __future__ import annotations

from typing import Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import KebaDataUpdateCoordinator
from .entity import KebaEntity
from .types import KebaConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEBA wallbox switches."""
    coordinator = entry.runtime_data
    async_add_entities([KebaChargerEnableSwitch(coordinator)])


def _schedule_refresh(coordinator: KebaDataUpdateCoordinator, name: str) -> None:
    """Refresh coordinator data without blocking the service response."""
    coordinator.hass.async_create_task(
        coordinator.async_request_refresh(),
        name=f"keba_wallbox_modbus refresh after {name} switch write",
    )


class KebaChargerEnableSwitch(RestoreEntity, KebaEntity, SwitchEntity):
    """Optimistic switch for enabling or disabling the wallbox."""

    _attr_name = "Charger enable"
    _attr_icon = "mdi:ev-plug-type2"

    def __init__(self, coordinator: KebaDataUpdateCoordinator) -> None:
        KebaEntity.__init__(self, coordinator, "charger_enable")
        self._is_on: Optional[bool] = None

    async def async_added_to_hass(self) -> None:
        """Restore the last commanded switch state."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        self._is_on = state.state == "on"

    @property
    def is_on(self) -> Optional[bool]:
        """Return the last commanded state."""
        return self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the wallbox."""
        await self.coordinator.async_write_register(5014, 1)
        self._is_on = True
        self.async_write_ha_state()
        _schedule_refresh(self.coordinator, "charger_enable")

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the wallbox."""
        await self.coordinator.async_write_register(5014, 0)
        self._is_on = False
        self.async_write_ha_state()
        _schedule_refresh(self.coordinator, "charger_enable")


class KebaChargingCurrentRegulationSwitch(RestoreEntity, KebaEntity, SwitchEntity):
    """Optimistic switch for charging current regulation."""

    _attr_name = "Charging current regulation"
    _attr_icon = "mdi:home-lightning-bolt-outline"

    def __init__(self, coordinator: KebaDataUpdateCoordinator) -> None:
        KebaEntity.__init__(self, coordinator, "charging_current_regulation")

    async def async_added_to_hass(self) -> None:
        """Restore the last commanded regulation state."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        self.coordinator.set_charging_current_regulation_enabled(state.state == "on")

    @property
    def is_on(self) -> bool:
        """Return whether charging current regulation is enabled."""
        return self.coordinator.charging_current_regulation_enabled

    async def async_turn_on(self, **kwargs) -> None:
        """Enable charging current regulation."""
        self.coordinator.set_charging_current_regulation_enabled(True)
        await self.coordinator.async_apply_charging_current_regulation()
        self.async_write_ha_state()
        _schedule_refresh(self.coordinator, "charging_current_regulation")

    async def async_turn_off(self, **kwargs) -> None:
        """Disable charging current regulation."""
        self.coordinator.set_charging_current_regulation_enabled(False)
        self.async_write_ha_state()
        _schedule_refresh(self.coordinator, "charging_current_regulation")
