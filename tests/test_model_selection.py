"""Regression tests for model overrides and empty P40 product registers."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.keba_wallbox_modbus.config_data import effective_config
from custom_components.keba_wallbox_modbus.const import CONF_MODEL, DOMAIN
from custom_components.keba_wallbox_modbus.coordinator import KebaDataUpdateCoordinator
from custom_components.keba_wallbox_modbus.decoding import describe_product
from custom_components.keba_wallbox_modbus.profiles import resolve_wallbox_model
from custom_components.keba_wallbox_modbus.registers import (
    KEY_FAST_CHARGING_STATE,
    KEY_FIRMWARE_VERSION,
    KEY_HARDWARE_REVISION_DEVICE,
    KEY_PRODUCT,
    KEY_SERIAL_NUMBER,
)


@pytest.mark.parametrize(
    ("product", "selection", "expected"),
    [
        (0, "auto", None),
        (312110, "auto", "p30"),
        (4212311, "auto", "p40"),
        (0, "p40", "p40"),
        (312110, "p40", "p40"),
        (4212311, "p30", "p30"),
    ],
)
def test_model_resolution(product, selection, expected):
    """Manual selection takes priority; automatic detection remains unchanged."""
    assert resolve_wallbox_model(product, selection) == expected


def test_existing_config_defaults_to_automatic():
    """Existing entries need no migration to keep automatic detection."""
    assert effective_config({}, {})[CONF_MODEL] == "auto"


@pytest.mark.parametrize("product", [0, None, 312110])
def test_override_does_not_invent_product_features(product):
    """An empty or conflicting product cannot describe P40 equipment."""
    assert "connector" not in describe_product(product, "p40")


async def test_p40_override_controls_polling_firmware_and_capabilities(hass):
    """Issue #5 uses the complete P40 profile when selected manually."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "wallbox.local"},
        options={CONF_MODEL: "p40"},
        unique_id="12345678",
    )
    coordinator = KebaDataUpdateCoordinator(hass, entry)
    values = {KEY_PRODUCT: 0, KEY_FIRMWARE_VERSION: 10500, KEY_SERIAL_NUMBER: 12345678}

    async def read(registers, **kwargs):
        return {key: values.get(key, 0) for key in registers}

    coordinator.hub.async_read_named_registers = AsyncMock(side_effect=read)
    coordinator.data = await coordinator._async_update_data()
    assert coordinator.model_key == "p40"
    assert coordinator.model == "KeContact P40"
    assert coordinator.firmware_version == "1.5.0"
    assert coordinator.capabilities.supports_fast_charging
    assert not coordinator.capabilities.supports_failsafe_persist
    assert not coordinator.capabilities.supports_unlock_plug
    assert coordinator.capabilities.connector is None
    assert KEY_FAST_CHARGING_STATE in coordinator.data
    assert KEY_HARDWARE_REVISION_DEVICE in coordinator.data

    # Subsequent polling must not reset the override when product remains zero.
    coordinator.data = await coordinator._async_update_data()
    assert coordinator.model_key == "p40"
    assert coordinator.firmware_version == "1.5.0"

    # Returning to automatic restores product-based detection.
    coordinator._config[CONF_MODEL] = "auto"
    coordinator.data[KEY_PRODUCT] = 312110
    coordinator.data[KEY_FIRMWARE_VERSION] = 0x030A0000
    coordinator.data = await coordinator._async_update_data()
    assert coordinator.model_key == "p30"
    assert coordinator.firmware_version == "3.10.0"
    assert not coordinator.capabilities.supports_fast_charging
    assert coordinator.capabilities.supports_failsafe_persist
