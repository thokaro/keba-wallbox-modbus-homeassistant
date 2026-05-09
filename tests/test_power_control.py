"""Tests for charging power control helpers."""

from __future__ import annotations

from custom_components.keba_wallbox_modbus.power_control import (
    charging_power_current_raw,
    power_per_amp,
    regulated_power_current_raw,
)
from custom_components.keba_wallbox_modbus.profiles import P30_PROFILE
from custom_components.keba_wallbox_modbus.registers import (
    KEY_ACTIVE_POWER,
    KEY_MAX_CHARGING_CURRENT,
    KEY_MAX_SUPPORTED_CURRENT,
    KEY_POWER_FACTOR,
    KEY_VOLTAGE_L1,
    KEY_VOLTAGE_L2,
    KEY_VOLTAGE_L3,
)


SCREENSHOT_DATA = {
    KEY_ACTIVE_POWER: 4_744_000,
    KEY_MAX_CHARGING_CURRENT: 7_400,
    KEY_MAX_SUPPORTED_CURRENT: 16_000,
    KEY_POWER_FACTOR: 998,
    KEY_VOLTAGE_L1: 226,
    KEY_VOLTAGE_L2: 225,
    KEY_VOLTAGE_L3: 225,
}


def test_power_per_amp_uses_voltage_sum_and_power_factor() -> None:
    """Watts per amp follows the currently measured wallbox values."""
    assert power_per_amp(SCREENSHOT_DATA, P30_PROFILE.model_key) == 676
    assert (
        power_per_amp(
            SCREENSHOT_DATA,
            P30_PROFILE.model_key,
            include_power_factor=True,
        )
        == 674.648
    )


def test_regulated_power_increases_current_limit_from_active_power_error() -> None:
    """Active-power regulation compensates when the car draws below the limit."""
    data = {
        **SCREENSHOT_DATA,
        KEY_ACTIVE_POWER: 4_300_000,
    }

    assert (
        regulated_power_current_raw(
            data,
            P30_PROFILE.model_key,
            P30_PROFILE,
            5.0,
        )
        == 7_800
    )


def test_charging_power_current_uses_direct_target_current() -> None:
    """Charging power writes the calculated target current immediately."""
    assert (
        charging_power_current_raw(
            SCREENSHOT_DATA,
            P30_PROFILE.model_key,
            P30_PROFILE,
            5.0,
        )
        == 7_400
    )


def test_charging_power_current_ignores_active_power() -> None:
    """The one-shot charging power write only uses voltage and power factor."""
    high_active_power = {
        **SCREENSHOT_DATA,
        KEY_ACTIVE_POWER: 6_700_000,
    }
    low_active_power = {
        **SCREENSHOT_DATA,
        KEY_ACTIVE_POWER: 500_000,
    }

    assert charging_power_current_raw(
        high_active_power,
        P30_PROFILE.model_key,
        P30_PROFILE,
        5.0,
    ) == charging_power_current_raw(
        low_active_power,
        P30_PROFILE.model_key,
        P30_PROFILE,
        5.0,
    )


def test_charging_power_current_can_suspend_charging() -> None:
    """A zero charging power target writes a zero current limit."""
    assert (
        charging_power_current_raw(
            SCREENSHOT_DATA,
            P30_PROFILE.model_key,
            P30_PROFILE,
            0,
        )
        == 0
    )


def test_charging_power_current_uses_nominal_fallback_without_data() -> None:
    """Charging power can still write once before polling data is available."""
    assert (
        charging_power_current_raw(
            None,
            P30_PROFILE.model_key,
            P30_PROFILE,
            5.0,
        )
        == 7_200
    )


def test_regulated_power_uses_direct_target_when_not_charging() -> None:
    """Regulation does not integrate upwards while active power is zero."""
    data = {
        **SCREENSHOT_DATA,
        KEY_ACTIVE_POWER: 0,
        KEY_MAX_CHARGING_CURRENT: 0,
    }

    assert (
        regulated_power_current_raw(
            data,
            P30_PROFILE.model_key,
            P30_PROFILE,
            5.0,
        )
        == 7_400
    )


def test_regulated_power_stays_put_inside_deadband() -> None:
    """Regulation avoids writes for small active-power deviations."""
    data = {
        **SCREENSHOT_DATA,
        KEY_ACTIVE_POWER: 4_930_000,
    }

    assert (
        regulated_power_current_raw(
            data,
            P30_PROFILE.model_key,
            P30_PROFILE,
            5.0,
        )
        is None
    )


def test_regulated_power_limits_large_active_power_corrections() -> None:
    """Regulation changes current gradually to avoid oscillation."""
    data = {
        **SCREENSHOT_DATA,
        KEY_ACTIVE_POWER: 6_500_000,
        KEY_MAX_CHARGING_CURRENT: 10_140,
    }

    assert (
        regulated_power_current_raw(
            data,
            P30_PROFILE.model_key,
            P30_PROFILE,
            7.0,
        )
        == 10_500
    )
