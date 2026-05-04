"""Tests for the KEBA Wallbox Modbus config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.keba_wallbox_modbus.const import (
    CONF_DISPLAY_MAX_TIME,
    CONF_DISPLAY_MIN_TIME,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UDP_HOST,
    CONF_UNIT_ID,
    DOMAIN,
    KEY_PRODUCT,
    KEY_SERIAL_NUMBER,
)

SERIAL = "12345678"

CONNECTION_INPUT = {
    CONF_HOST: "wallbox.local",
    CONF_PORT: 502,
    CONF_UDP_HOST: "",
    CONF_UNIT_ID: 255,
    CONF_TIMEOUT: 5,
}
OPTION_INPUT = {
    CONF_SCAN_INTERVAL: 30,
    CONF_DISPLAY_MIN_TIME: 2,
    CONF_DISPLAY_MAX_TIME: 10,
}
USER_INPUT = {**CONNECTION_INPUT, **OPTION_INPUT}
PROBE_RESULT = {
    KEY_SERIAL_NUMBER: int(SERIAL),
    KEY_PRODUCT: 312110,
}


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
            data=USER_INPUT,
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"KeContact P30 {SERIAL}"
    assert result["data"] == {
        **CONNECTION_INPUT,
        CONF_UDP_HOST: CONNECTION_INPUT[CONF_HOST],
    }
    assert result["options"] == OPTION_INPUT


async def test_options_flow_updates_only_runtime_options(
    hass: HomeAssistant,
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
        CONF_SCAN_INTERVAL: 45,
        CONF_DISPLAY_MIN_TIME: 1,
        CONF_DISPLAY_MAX_TIME: 8,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=options,
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
            user_input=updated,
        )

    assert result["type"] == FlowResultType.ABORT
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
            user_input=CONNECTION_INPUT,
        )

    assert result["type"] == FlowResultType.ABORT
    assert entry.data[CONF_HOST] == CONNECTION_INPUT[CONF_HOST]
