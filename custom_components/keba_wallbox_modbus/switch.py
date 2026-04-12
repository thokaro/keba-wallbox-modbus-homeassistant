"""Switch platform for KEBA Wallbox Modbus."""

from __future__ import annotations

from typing import Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import KebaDataUpdateCoordinator
from .entity import KebaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEBA wallbox switches."""
    coordinator: KebaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KebaChargerEnableSwitch(coordinator)])


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
        await self.coordinator.async_write_register_and_refresh(5014, 1)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the wallbox."""
        await self.coordinator.async_write_register_and_refresh(5014, 0)
        self._is_on = False
        self.async_write_ha_state()
