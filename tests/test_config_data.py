"""Tests for config entry data helpers."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.keba_wallbox_modbus.config_data import option_defaults, split_config
from custom_components.keba_wallbox_modbus.const import (
    CONF_DISPLAY_MAX_TIME,
    CONF_DISPLAY_MIN_TIME,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UDP_HOST,
    CONF_UNIT_ID,
)


def test_option_defaults_use_15_second_scan_interval() -> None:
    """New entries default to a 15 second polling interval."""
    assert option_defaults({})[CONF_SCAN_INTERVAL] == 15


def test_split_config_preserves_legacy_effective_values() -> None:
    """Options from legacy entries keep overriding data during migration."""
    data, options = split_config(
        {
            CONF_HOST: "old-host",
            CONF_PORT: 502,
            CONF_UDP_HOST: "old-udp",
            CONF_UNIT_ID: 255,
            CONF_TIMEOUT: 5,
            CONF_SCAN_INTERVAL: 30,
            CONF_DISPLAY_MIN_TIME: 2,
            CONF_DISPLAY_MAX_TIME: 10,
        },
        {
            CONF_HOST: "new-host",
            CONF_SCAN_INTERVAL: 60,
            CONF_DISPLAY_MIN_TIME: 1,
        },
    )

    assert data == {
        CONF_HOST: "new-host",
        CONF_PORT: 502,
        CONF_UDP_HOST: "old-udp",
        CONF_UNIT_ID: 255,
        CONF_TIMEOUT: 5,
    }
    assert options == {
        CONF_SCAN_INTERVAL: 60,
        CONF_DISPLAY_MIN_TIME: 1,
        CONF_DISPLAY_MAX_TIME: 10,
    }
