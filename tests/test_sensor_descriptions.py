"""Tests for KEBA sensor descriptions."""

from __future__ import annotations

from homeassistant.helpers.entity import EntityCategory

from custom_components.keba_wallbox_modbus.registers import (
    KEY_CABLE_STATE,
    KEY_CHARGER_STATUS,
    KEY_CHARGING_STATE,
    KEY_PHASE_SWITCH_STATE,
)
from custom_components.keba_wallbox_modbus.sensor_descriptions import (
    SENSOR_DESCRIPTIONS,
)


def _sensor_description(key: str):
    """Return a sensor description by key."""
    return next(
        description for description in SENSOR_DESCRIPTIONS if description.key == key
    )


def test_charger_status_interprets_charging_state() -> None:
    """Charger status exposes IEC A/B/C states derived from wallbox state."""
    description = _sensor_description(KEY_CHARGER_STATUS)

    assert description.options == ("A", "B", "C")
    assert description.value_fn(
        None, {KEY_CHARGING_STATE: 2, KEY_CABLE_STATE: 0}
    ) == "A"
    assert description.value_fn(
        None, {KEY_CHARGING_STATE: 2, KEY_CABLE_STATE: 5}
    ) == "B"
    assert description.value_fn(
        None, {KEY_CHARGING_STATE: 3, KEY_CABLE_STATE: 7}
    ) == "C"
    assert description.value_fn(None, {KEY_CHARGING_STATE: 1}) == "A"
    assert description.value_fn(None, {KEY_CHARGING_STATE: 5}) == "B"
    assert description.value_fn(None, {KEY_CHARGING_STATE: 4}) is None


def test_phase_switch_state_is_diagnostic_sensor() -> None:
    """Phase switch state exposes the read register as a diagnostic sensor."""
    description = _sensor_description(KEY_PHASE_SWITCH_STATE)

    assert description.entity_category is EntityCategory.DIAGNOSTIC
    assert description.options == ("1", "3")
    assert description.value_fn(None, {KEY_PHASE_SWITCH_STATE: 1}) == "1"
    assert description.value_fn(None, {KEY_PHASE_SWITCH_STATE: 3}) == "3"
    assert description.value_fn(None, {KEY_PHASE_SWITCH_STATE: 0}) is None
