"""The KEBA Wallbox Modbus integration."""

from __future__ import annotations

from homeassistant.config import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .config_data import split_config
from .const import PLATFORMS
from .coordinator import KebaDataUpdateCoordinator
from .types import KebaConfigEntry


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up KEBA Wallbox Modbus."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KebaConfigEntry) -> bool:
    """Set up KEBA Wallbox Modbus from a config entry."""
    coordinator = KebaDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KebaConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_shutdown()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries to the current data/options layout."""
    if entry.version > 1:
        return False

    if entry.minor_version >= 2:
        return True

    new_data, new_options = split_config(dict(entry.data), dict(entry.options))
    hass.config_entries.async_update_entry(
        entry,
        data=new_data,
        options=new_options,
        version=1,
        minor_version=2,
    )
    return True
