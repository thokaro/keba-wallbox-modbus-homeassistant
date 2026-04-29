"""Config flow for KEBA Wallbox Modbus."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector

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
    DOMAIN,
    KEY_PRODUCT,
    KEY_SERIAL_NUMBER,
    UDP_DISPLAY_MAX_DURATION,
    detect_wallbox_model,
    format_serial_number,
    model_name_for_key,
)
from .modbus import KebaModbusError, async_probe_device

LOGGER = logging.getLogger(__name__)


def _normalize_user_input(user_input: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize selector output before probing or storing it."""
    return {
        CONF_HOST: str(user_input[CONF_HOST]),
        CONF_PORT: int(user_input[CONF_PORT]),
        CONF_UDP_HOST: str(user_input.get(CONF_UDP_HOST, user_input[CONF_HOST])),
        CONF_UNIT_ID: int(user_input[CONF_UNIT_ID]),
        CONF_TIMEOUT: int(user_input[CONF_TIMEOUT]),
        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
        CONF_DISPLAY_MIN_TIME: int(user_input[CONF_DISPLAY_MIN_TIME]),
        CONF_DISPLAY_MAX_TIME: int(user_input[CONF_DISPLAY_MAX_TIME]),
    }


def _validate_display_defaults(user_input: Dict[str, Any]) -> dict[str, str]:
    """Validate display duration defaults."""
    if int(user_input[CONF_DISPLAY_MIN_TIME]) > int(user_input[CONF_DISPLAY_MAX_TIME]):
        return {"base": "invalid_display_duration"}

    return {}


def _build_schema(defaults: Optional[Dict[str, Any]] = None) -> vol.Schema:
    """Build the config schema."""
    values = defaults or {}

    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=values.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=values.get(CONF_PORT, DEFAULT_PORT)): (
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=65535,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                )
            ),
            vol.Optional(
                CONF_UDP_HOST,
                default=values.get(CONF_UDP_HOST, values.get(CONF_HOST, "")),
            ): str,
            vol.Required(CONF_UNIT_ID, default=values.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)): (
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=255,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                )
            ),
            vol.Required(CONF_TIMEOUT, default=values.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)): (
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=30,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                )
            ),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=values.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5,
                    max=3600,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_DISPLAY_MIN_TIME,
                default=values.get(CONF_DISPLAY_MIN_TIME, DEFAULT_DISPLAY_MIN_TIME),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=UDP_DISPLAY_MAX_DURATION,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_DISPLAY_MAX_TIME,
                default=values.get(CONF_DISPLAY_MAX_TIME, DEFAULT_DISPLAY_MAX_TIME),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=UDP_DISPLAY_MAX_DURATION,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


async def _async_probe_user_input(
    user_input: Dict[str, Any],
    *,
    context: str,
) -> tuple[Optional[Dict[str, Optional[int]]], dict[str, str]]:
    """Probe a wallbox using config flow input."""
    try:
        probe = await async_probe_device(
            str(user_input[CONF_HOST]),
            int(user_input[CONF_PORT]),
            int(user_input[CONF_TIMEOUT]),
            int(user_input[CONF_UNIT_ID]),
        )
    except KebaModbusError as err:
        LOGGER.warning(
            "KEBA wallbox %s failed for %s:%s: %s",
            context,
            user_input[CONF_HOST],
            user_input[CONF_PORT],
            err,
        )
        return None, {"base": "cannot_connect"}
    except Exception:  # pragma: no cover - defensive guard
        LOGGER.exception("Unexpected error during KEBA wallbox %s", context)
        return None, {"base": "unknown"}

    return probe, {}


def _probe_identity(probe: Dict[str, Optional[int]]) -> tuple[Optional[str], str]:
    """Extract the serial number and model name from a probe result."""
    serial = format_serial_number(probe.get(KEY_SERIAL_NUMBER))
    model_name = model_name_for_key(detect_wallbox_model(probe.get(KEY_PRODUCT)))
    return serial, model_name


class KebaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KEBA Wallbox Modbus."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return KebaOptionsFlow(config_entry)

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized_input = _normalize_user_input(user_input)
            errors = _validate_display_defaults(normalized_input)
            if not errors:
                probe, errors = await _async_probe_user_input(
                    normalized_input,
                    context="discovery",
                )
                if probe is not None:
                    serial, model_name = _probe_identity(probe)
                    if serial is None:
                        errors["base"] = "cannot_connect"
                    else:
                        await self.async_set_unique_id(serial)
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title=f"{model_name} {serial}",
                            data=normalized_input,
                        )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input),
            errors=errors,
        )


class KebaOptionsFlow(OptionsFlow):
    """Handle KEBA Wallbox Modbus options."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None):
        """Manage the options flow."""
        defaults = {**self._entry.data, **self._entry.options}
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized_input = _normalize_user_input(user_input)
            errors = _validate_display_defaults(normalized_input)
            if not errors:
                probe, errors = await _async_probe_user_input(
                    normalized_input,
                    context="option validation",
                )
                if probe is not None:
                    serial, _ = _probe_identity(probe)
                    if serial is None:
                        errors["base"] = "cannot_connect"
                    elif (
                        self._entry.unique_id is not None
                        and serial != self._entry.unique_id
                    ):
                        errors["base"] = "different_device"
                    else:
                        return self.async_create_entry(title="", data=normalized_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults),
            errors=errors,
        )
