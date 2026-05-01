"""Diagnostics support for KEBA Wallbox Modbus."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import (
    CONF_UDP_HOST,
    DOMAIN,
    KEY_PRODUCT,
    KEY_SERIAL_NUMBER,
    describe_product,
)
from .coordinator import KebaDataUpdateCoordinator

TO_REDACT = {
    CONF_HOST,
    CONF_PORT,
    CONF_UDP_HOST,
    KEY_SERIAL_NUMBER,
    "unique_id",
}
REDACTED = "**REDACTED**"


def _redact_text(text: str | None, entry: ConfigEntry) -> str | None:
    """Redact known sensitive values from free-form text."""
    if text is None:
        return None

    redacted = text
    if entry.unique_id is not None:
        redacted = redacted.replace(entry.unique_id, REDACTED)

    for config in (entry.data, entry.options):
        for key in (CONF_HOST, CONF_UDP_HOST):
            value = config.get(key)
            if value is not None:
                redacted = redacted.replace(str(value), REDACTED)

    return redacted


def _format_last_exception(
    coordinator: KebaDataUpdateCoordinator,
    entry: ConfigEntry,
) -> dict[str, str | None] | None:
    """Return a redacted representation of the last coordinator exception."""
    if coordinator.last_exception is None:
        return None

    return {
        "type": type(coordinator.last_exception).__name__,
        "message": _redact_text(str(coordinator.last_exception), entry),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: KebaDataUpdateCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )

    diagnostics: dict[str, Any] = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": _redact_text(entry.title, entry),
            "unique_id": entry.unique_id,
            "data": dict(entry.data),
            "options": dict(entry.options),
        }
    }

    if coordinator is None:
        diagnostics["coordinator"] = {"loaded": False}
        return async_redact_data(diagnostics, TO_REDACT)

    data = dict(coordinator.data or {})
    capabilities = coordinator.capabilities
    profile = coordinator.profile

    diagnostics["coordinator"] = {
        "loaded": True,
        "last_update_success": coordinator.last_update_success,
        "last_exception": _format_last_exception(coordinator, entry),
        "update_interval": coordinator.update_interval.total_seconds()
        if coordinator.update_interval is not None
        else None,
        "device": {
            "model": coordinator.model,
            "model_key": coordinator.model_key,
            "serial_number": coordinator.device_serial,
            "firmware_version": coordinator.firmware_version,
            "firmware_version_raw": coordinator.firmware_version_raw,
            "product": describe_product(data.get(KEY_PRODUCT), coordinator.model_key),
        },
        "capabilities": asdict(capabilities),
        "profile": {
            "model_key": profile.model_key,
            "model_name": profile.model_name,
            "static_register_map": dict(profile.static_register_map),
            "runtime_register_map": dict(profile.runtime_register_map),
            "optional_runtime_keys": sorted(profile.optional_runtime_keys),
            "supports_failsafe_persist": profile.supports_failsafe_persist,
            "supports_fast_charging": profile.supports_fast_charging,
            "charging_current_min_amps": profile.charging_current_min_amps,
        },
        "data": data,
    }

    return async_redact_data(diagnostics, TO_REDACT)
