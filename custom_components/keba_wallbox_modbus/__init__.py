"""The KEBA Wallbox Modbus integration."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components import notify as hass_notify
from homeassistant.config import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import discovery

from .const import (
    DATA_HASS_CONFIG,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import KebaDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Store Home Assistant config for later notify discovery."""
    hass.data[DATA_HASS_CONFIG] = config
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KEBA Wallbox Modbus from a config entry."""
    coordinator = KebaDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        hass.async_create_task(_async_load_notify_platform(hass, coordinator)).cancel
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: KebaDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
        await hass_notify.async_reload(hass, DOMAIN)

        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_notify_service_name(
    hass: HomeAssistant, coordinator: KebaDataUpdateCoordinator
) -> str:
    """Return the preferred notify service name for this wallbox."""
    unique_root = coordinator.entry.unique_id or coordinator.entry.entry_id
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, unique_root)})

    if device is not None:
        return device.name_by_user or device.name or coordinator.entry.title

    return coordinator.entry.title


async def _async_load_notify_platform(
    hass: HomeAssistant, coordinator: KebaDataUpdateCoordinator
) -> None:
    """Load the legacy notify platform after the device name becomes available."""
    if not await coordinator.async_probe_display_support():
        LOGGER.debug(
            "Skipping KEBA notify platform for entry %s because no display support was detected",
            coordinator.entry.entry_id,
        )
        return

    service_name = coordinator.entry.title

    for _ in range(10):
        service_name = _get_notify_service_name(hass, coordinator)
        if service_name != coordinator.entry.title:
            break
        await asyncio.sleep(0.5)

    LOGGER.debug(
        "Loading KEBA notify platform '%s' for entry %s",
        service_name,
        coordinator.entry.entry_id,
    )
    await discovery.async_load_platform(
        hass,
        Platform.NOTIFY,
        DOMAIN,
        {
            CONF_NAME: service_name,
            ATTR_CONFIG_ENTRY_ID: coordinator.entry.entry_id,
        },
        hass.data.get(DATA_HASS_CONFIG, {}),
    )
