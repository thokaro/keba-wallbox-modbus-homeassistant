"""Config flow for KEBA Wallbox Modbus."""

from __future__ import annotations

import logging
from typing import Any, Optional

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector

from .config_data import connection_defaults, option_defaults
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


def _normalize_connection_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize connection selector output before probing or storing it."""
    host = str(user_input[CONF_HOST])
    return {
        CONF_HOST: host,
        CONF_PORT: int(user_input[CONF_PORT]),
        CONF_UDP_HOST: str(user_input.get(CONF_UDP_HOST) or host),
        CONF_UNIT_ID: int(user_input[CONF_UNIT_ID]),
        CONF_TIMEOUT: int(user_input[CONF_TIMEOUT]),
    }


def _normalize_option_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize option selector output before storing it."""
    return {
        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
        CONF_DISPLAY_MIN_TIME: int(user_input[CONF_DISPLAY_MIN_TIME]),
        CONF_DISPLAY_MAX_TIME: int(user_input[CONF_DISPLAY_MAX_TIME]),
    }


def _validate_display_defaults(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate display duration defaults."""
    if int(user_input[CONF_DISPLAY_MIN_TIME]) > int(user_input[CONF_DISPLAY_MAX_TIME]):
        return {"base": "invalid_display_duration"}

    return {}


def _connection_schema(defaults: Optional[dict[str, Any]] = None) -> dict[Any, Any]:
    """Build the connection part of a config schema."""
    values = connection_defaults(defaults)
    return {
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
    }


def _option_schema(defaults: Optional[dict[str, Any]] = None) -> dict[Any, Any]:
    """Build the options part of a config schema."""
    values = option_defaults(defaults)
    return {
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


def _build_setup_schema(defaults: Optional[dict[str, Any]] = None) -> vol.Schema:
    """Build the initial config schema."""
    return vol.Schema({**_connection_schema(defaults), **_option_schema(defaults)})


def _build_reconfigure_schema(defaults: Optional[dict[str, Any]] = None) -> vol.Schema:
    """Build the reconfigure schema for setup data."""
    return vol.Schema(_connection_schema(defaults))


def _build_options_schema(defaults: Optional[dict[str, Any]] = None) -> vol.Schema:
    """Build the options schema."""
    return vol.Schema(_option_schema(defaults))


async def _async_probe_user_input(
    user_input: dict[str, Any],
    *,
    context: str,
) -> tuple[Optional[dict[str, Optional[int]]], dict[str, str]]:
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


def _probe_identity(probe: dict[str, Optional[int]]) -> tuple[Optional[str], str]:
    """Extract the serial number and model name from a probe result."""
    serial = format_serial_number(probe.get(KEY_SERIAL_NUMBER))
    model_name = model_name_for_key(detect_wallbox_model(probe.get(KEY_PRODUCT)))
    return serial, model_name


class KebaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KEBA Wallbox Modbus."""

    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return KebaOptionsFlow(config_entry)

    async def async_step_user(self, user_input: Optional[dict[str, Any]] = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            connection_input = _normalize_connection_input(user_input)
            option_input = _normalize_option_input(user_input)
            errors = _validate_display_defaults(option_input)
            if not errors:
                probe, errors = await _async_probe_user_input(
                    connection_input,
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
                            data=connection_input,
                            options=option_input,
                        )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_setup_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: Optional[dict[str, Any]] = None,
    ):
        """Handle reconfiguration of connection data."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            connection_input = _normalize_connection_input(user_input)
            probe, errors = await _async_probe_user_input(
                connection_input,
                context="reconfiguration",
            )
            if probe is not None:
                serial, _ = _probe_identity(probe)
                if serial is None:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates=connection_input,
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_reconfigure_schema(user_input or dict(entry.data)),
            errors=errors,
        )


class KebaOptionsFlow(OptionsFlow):
    """Handle KEBA Wallbox Modbus options."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: Optional[dict[str, Any]] = None):
        """Manage the options flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            option_input = _normalize_option_input(user_input)
            errors = _validate_display_defaults(option_input)
            if not errors:
                return self.async_create_entry(title="", data=option_input)

        defaults = user_input or {**dict(self._entry.data), **dict(self._entry.options)}
        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_schema(defaults),
            errors=errors,
        )
