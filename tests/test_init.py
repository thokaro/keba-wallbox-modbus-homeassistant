"""Tests for integration setup helpers."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.keba_wallbox_modbus import async_migrate_entry
from custom_components.keba_wallbox_modbus.const import (
    CONF_DISPLAY_MAX_TIME,
    CONF_DISPLAY_MIN_TIME,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UDP_HOST,
    CONF_UNIT_ID,
    DOMAIN,
)


async def test_migrate_entry_splits_legacy_data_and_options(
    hass: HomeAssistant,
) -> None:
    """Migration keeps the effective legacy config while splitting storage."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "old-host",
            CONF_PORT: 502,
            CONF_UDP_HOST: "old-host",
            CONF_UNIT_ID: 255,
            CONF_TIMEOUT: 5,
            CONF_SCAN_INTERVAL: 30,
            CONF_DISPLAY_MIN_TIME: 2,
            CONF_DISPLAY_MAX_TIME: 10,
        },
        options={
            CONF_HOST: "new-host",
            CONF_UDP_HOST: "display-host",
            CONF_SCAN_INTERVAL: 60,
        },
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.data == {
        CONF_HOST: "new-host",
        CONF_PORT: 502,
        CONF_UDP_HOST: "display-host",
        CONF_UNIT_ID: 255,
        CONF_TIMEOUT: 5,
    }
    assert entry.options == {
        CONF_SCAN_INTERVAL: 60,
        CONF_DISPLAY_MIN_TIME: 2,
        CONF_DISPLAY_MAX_TIME: 10,
    }
    assert entry.minor_version == 2
