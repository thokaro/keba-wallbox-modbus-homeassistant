"""The KEBA Wallbox Modbus integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service

from .const import DOMAIN, PLATFORMS, UDP_DISPLAY_MAX_DURATION
from .coordinator import KebaDataUpdateCoordinator

ATTR_MAX_TIME = "max_time"
ATTR_MESSAGE = "message"
ATTR_MIN_TIME = "min_time"

SERVICE_DISPLAY_MESSAGE = "display_message"
DISPLAY_TIME_SCHEMA = vol.All(
    vol.Coerce(float),
    vol.Range(min=0, max=UDP_DISPLAY_MAX_DURATION),
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up KEBA Wallbox Modbus services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DISPLAY_MESSAGE,
        entity_domain=Platform.NOTIFY,
        schema={
            vol.Required(ATTR_MESSAGE): cv.string,
            vol.Optional(ATTR_MIN_TIME): DISPLAY_TIME_SCHEMA,
            vol.Optional(ATTR_MAX_TIME): DISPLAY_TIME_SCHEMA,
        },
        func="async_display_message",
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KEBA Wallbox Modbus from a config entry."""
    coordinator = KebaDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: KebaDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
