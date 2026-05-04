"""Configuration data helpers for KEBA Wallbox Modbus."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    CONF_DISPLAY_MAX_TIME,
    CONF_DISPLAY_MIN_TIME,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UDP_HOST,
    CONF_UNIT_ID,
    DEFAULT_DISPLAY_MAX_TIME,
    DEFAULT_DISPLAY_MIN_TIME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_UNIT_ID,
)

CONNECTION_KEYS = (
    CONF_HOST,
    CONF_PORT,
    CONF_UDP_HOST,
    CONF_UNIT_ID,
    CONF_TIMEOUT,
)
OPTION_KEYS = (
    CONF_SCAN_INTERVAL,
    CONF_DISPLAY_MIN_TIME,
    CONF_DISPLAY_MAX_TIME,
)


def connection_defaults(values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return complete connection defaults merged with stored values."""
    stored = values or {}
    host = str(stored.get(CONF_HOST, ""))
    return {
        CONF_HOST: host,
        CONF_PORT: int(stored.get(CONF_PORT, DEFAULT_PORT)),
        CONF_UDP_HOST: str(stored.get(CONF_UDP_HOST, host)),
        CONF_UNIT_ID: int(stored.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)),
        CONF_TIMEOUT: int(stored.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
    }


def option_defaults(values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return complete option defaults merged with stored values."""
    stored = values or {}
    return {
        CONF_SCAN_INTERVAL: int(stored.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        CONF_DISPLAY_MIN_TIME: int(
            stored.get(CONF_DISPLAY_MIN_TIME, DEFAULT_DISPLAY_MIN_TIME)
        ),
        CONF_DISPLAY_MAX_TIME: int(
            stored.get(CONF_DISPLAY_MAX_TIME, DEFAULT_DISPLAY_MAX_TIME)
        ),
    }


def effective_config(data: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    """Return the complete runtime configuration for a config entry."""
    legacy_values = {**data, **options}
    return {
        **connection_defaults(legacy_values),
        **option_defaults(legacy_values),
    }


def split_config(
    data: dict[str, Any],
    options: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split legacy mixed config entry values into data and options."""
    values = effective_config(data, options)
    return (
        {key: values[key] for key in CONNECTION_KEYS},
        {key: values[key] for key in OPTION_KEYS},
    )
