"""Tests for writable KEBA entity descriptions."""

from __future__ import annotations

from custom_components.keba_wallbox_modbus.write_descriptions import NUMBER_DESCRIPTIONS


def _number_description(key: str):
    return next(
        description for description in NUMBER_DESCRIPTIONS if description.key == key
    )


def test_charging_current_limit_uses_tenth_amp_steps() -> None:
    """Charging current limit can be adjusted in tenth amp steps."""
    description = _number_description("charging_current_limit")

    assert description.native_step == 0.1
    assert description.to_raw_fn(None, 6.6) == 6600
    assert description.from_raw_fn is not None
    assert description.from_raw_fn(None, 6600) == 6.6


def test_charging_power_is_available_as_target() -> None:
    """Charging power is exposed as an optimistic kW regulation target."""
    description = _number_description("charging_power")

    assert description.name == "Charging power"
    assert description.native_step == 0.01
    assert description.optimistic


def test_charging_power_slider_is_not_exposed() -> None:
    """The previous convenience slider is no longer exposed."""
    assert not any(
        description.key == "charging_power_limit"
        for description in NUMBER_DESCRIPTIONS
    )


def test_regulated_charging_power_key_is_not_exposed() -> None:
    """The unpublished internal key is no longer exposed."""
    assert not any(
        description.key == "regulated_charging_power"
        for description in NUMBER_DESCRIPTIONS
    )


def test_failsafe_current_uses_supported_icon() -> None:
    """Failsafe current uses a stable shield icon."""
    description = _number_description("failsafe_current")

    assert description.icon == "mdi:shield-alert-outline"


def test_failsafe_current_uses_tenth_amp_steps() -> None:
    """Failsafe current can be adjusted in tenth amp steps."""
    description = _number_description("failsafe_current")

    assert description.native_step == 0.1
    assert description.to_raw_fn(None, 6.6) == 6600
