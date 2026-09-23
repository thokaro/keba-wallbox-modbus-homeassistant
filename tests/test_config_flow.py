"""Tests for the KEBA Wallbox Modbus config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.keba_wallbox_modbus.config_flow import _option_schema, SECTION_P30_UDP, UDP_FIELDS
from custom_components.keba_wallbox_modbus.const import (
    CONF_DISPLAY_MAX_TIME,
    CONF_DISPLAY_MIN_TIME,
    CONF_SCAN_INTERVAL,
    CONF_SLOW_RUNTIME_POLL_INTERVAL,
    CONF_TIMEOUT,
    CONF_UDP_HOST,
    CONF_UNIT_ID,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from custom_components.keba_wallbox_modbus.registers import KEY_PRODUCT, KEY_SERIAL_NUMBER

SERIAL = "12345678"

CONNECTION_INPUT = {
    CONF_HOST: "wallbox.local",
    CONF_PORT: 502,
    CONF_UDP_HOST: "",
    CONF_UNIT_ID: 255,
    CONF_TIMEOUT: 5,
}
OPTION_INPUT = {
    "model": "auto",
    CONF_SCAN_INTERVAL: 30,
    CONF_SLOW_RUNTIME_POLL_INTERVAL: 300,
    CONF_DISPLAY_MIN_TIME: 2,
    CONF_DISPLAY_MAX_TIME: 10,
}
USER_INPUT = {**CONNECTION_INPUT, **OPTION_INPUT}
PROBE_RESULT = {
    KEY_SERIAL_NUMBER: int(SERIAL),
    KEY_PRODUCT: 312110,
}


def with_udp_section(values):
    """Submit values using the same nesting as the configuration form."""
    return {
        **{key: value for key, value in values.items() if key not in UDP_FIELDS},
        SECTION_P30_UDP: {key: value for key, value in values.items() if key in UDP_FIELDS},
    }


def test_options_schema_uses_minimum_scan_interval() -> None:
    """The options flow enforces the documented minimum scan interval."""
    selector = next(
        selector
        for key, selector in _option_schema().items()
        if getattr(key, "schema", None) == CONF_SCAN_INTERVAL
    )

    assert selector.config["min"] == MIN_SCAN_INTERVAL


def test_options_schema_exposes_slow_runtime_poll_interval() -> None:
    """The options flow exposes the slow runtime polling interval."""
    selector = next(
        selector
        for key, selector in _option_schema().items()
        if getattr(key, "schema", None) == CONF_SLOW_RUNTIME_POLL_INTERVAL
    )

    assert selector.config["min"] == MIN_SCAN_INTERVAL
    assert selector.config["max"] == 3600


async def test_user_flow_stores_connection_data_and_options(
    hass: HomeAssistant,
) -> None:
    """The initial flow stores connection data separately from options."""
    with patch(
        "custom_components.keba_wallbox_modbus.config_flow.async_probe_device",
        return_value=PROBE_RESULT,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=with_udp_section(USER_INPUT),
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"KeContact P30 {SERIAL}"
    assert result["data"] == {
        **CONNECTION_INPUT,
        CONF_UDP_HOST: CONNECTION_INPUT[CONF_HOST],
    }
    assert result["options"] == OPTION_INPUT


@pytest.mark.parametrize("model", ["auto", "p30", "p40"])
async def test_options_flow_updates_only_runtime_options(
    hass: HomeAssistant, model: str,
) -> None:
    """The options flow no longer edits connection data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"KeContact P30 {SERIAL}",
        data={**CONNECTION_INPUT, CONF_UDP_HOST: CONNECTION_INPUT[CONF_HOST]},
        options=OPTION_INPUT,
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    options = {
        "model": model,
        CONF_SCAN_INTERVAL: 45,
        CONF_SLOW_RUNTIME_POLL_INTERVAL: 60,
        CONF_DISPLAY_MIN_TIME: 1,
        CONF_DISPLAY_MAX_TIME: 8,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=with_udp_section(options),
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == options


async def test_reconfigure_flow_updates_connection_data(
    hass: HomeAssistant,
) -> None:
    """The reconfigure flow validates identity before updating data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"KeContact P30 {SERIAL}",
        data={**CONNECTION_INPUT, CONF_UDP_HOST: CONNECTION_INPUT[CONF_HOST]},
        options=OPTION_INPUT,
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM

    updated = {
        **CONNECTION_INPUT,
        CONF_HOST: "new-wallbox.local",
        CONF_UDP_HOST: "display.local",
    }
    with patch(
        "custom_components.keba_wallbox_modbus.config_flow.async_probe_device",
        return_value=PROBE_RESULT,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=with_udp_section(updated),
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == updated
    assert entry.options == OPTION_INPUT


async def test_reconfigure_flow_rejects_different_device(
    hass: HomeAssistant,
) -> None:
    """Reconfigure aborts before changing data when the serial number changes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"KeContact P30 {SERIAL}",
        data={**CONNECTION_INPUT, CONF_UDP_HOST: CONNECTION_INPUT[CONF_HOST]},
        options=OPTION_INPUT,
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    with patch(
        "custom_components.keba_wallbox_modbus.config_flow.async_probe_device",
        return_value={**PROBE_RESULT, KEY_SERIAL_NUMBER: 87654321},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=with_udp_section(CONNECTION_INPUT),
        )

    assert result["type"] == FlowResultType.ABORT
    assert entry.data[CONF_HOST] == CONNECTION_INPUT[CONF_HOST]


async def test_user_flow_manual_p40_with_empty_product(hass: HomeAssistant) -> None:
    """A manual model controls setup identity even with an empty product register."""
    with patch(
        "custom_components.keba_wallbox_modbus.config_flow.async_probe_device",
        return_value={**PROBE_RESULT, KEY_PRODUCT: 0},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=with_udp_section({**USER_INPUT, "model": "p40"}),
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"KeContact P40 {SERIAL}"
    assert result["options"]["model"] == "p40"
    assert result["result"].unique_id == SERIAL


async def test_collapsed_options_keep_stored_display_durations(hass):
    """Saving without opening the section retains existing display settings."""
    options = {**OPTION_INPUT, CONF_DISPLAY_MIN_TIME: 3, CONF_DISPLAY_MAX_TIME: 9}
    entry = MockConfigEntry(domain=DOMAIN, data=CONNECTION_INPUT, options=options)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    udp_section = result["data_schema"].schema[SECTION_P30_UDP]
    assert udp_section.options["collapsed"] is True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={key: value for key, value in options.items() if key not in UDP_FIELDS},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == options


async def test_invalid_display_durations_preserve_section_values(hass):
    """Validation still rejects invalid nested durations and retains the input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER},
    )
    assert result["data_schema"].schema[SECTION_P30_UDP].options["collapsed"] is True
    invalid = with_udp_section({**USER_INPUT, CONF_DISPLAY_MIN_TIME: 9, CONF_DISPLAY_MAX_TIME: 2})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=invalid)
    assert result["errors"] == {"base": "invalid_display_duration"}
    assert result["data_schema"](invalid)[SECTION_P30_UDP] == invalid[SECTION_P30_UDP]
    defaults = result["data_schema"].schema[SECTION_P30_UDP].schema({})
    assert defaults[CONF_DISPLAY_MIN_TIME] == 9
    assert defaults[CONF_DISPLAY_MAX_TIME] == 2


@pytest.mark.parametrize("stored", [{}, {CONF_DISPLAY_MIN_TIME: 0, CONF_DISPLAY_MAX_TIME: 7}])
@pytest.mark.parametrize("form", ["setup", "options"])
def test_udp_section_serializes_complete_frontend_defaults(stored, form):
    """The section default must not mask its fields' values in the frontend."""
    from probatio import to_field_list
    from homeassistant.helpers.config_validation import custom_serializer

    from custom_components.keba_wallbox_modbus.config_flow import (
        _build_options_schema,
        _build_setup_schema,
    )

    build = _build_setup_schema if form == "setup" else _build_options_schema
    fields = to_field_list(build(stored), custom_serializer=custom_serializer)
    udp = next(field for field in fields if field["name"] == SECTION_P30_UDP)
    assert udp["type"] == "expandable"
    assert udp["expanded"] is False
    assert udp["default"][CONF_DISPLAY_MIN_TIME] == stored.get(CONF_DISPLAY_MIN_TIME, 2)
    assert udp["default"][CONF_DISPLAY_MAX_TIME] == stored.get(CONF_DISPLAY_MAX_TIME, 10)
