"""Power-to-current conversion helpers for KEBA wallboxes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from .base import MODEL_KEY_P40
from .decoding import scale_milliamps, scale_milliwatts
from .profiles import KebaProfile
from .registers import (
    KEY_ACTIVE_POWER,
    KEY_MAX_CHARGING_CURRENT,
    KEY_MAX_SUPPORTED_CURRENT,
    KEY_PHASE_SWITCH_STATE,
    KEY_POWER_FACTOR,
    KEY_PRODUCT,
    KEY_VOLTAGE_L1,
    KEY_VOLTAGE_L2,
    KEY_VOLTAGE_L3,
)

NOMINAL_PHASE_VOLTAGE = 230
REGULATED_POWER_CURRENT_STEP_AMPS = 0.1
REGULATED_POWER_GAIN = 0.425
REGULATED_POWER_MAX_CHANGE_AMPS = 0.5
REGULATED_POWER_MIN_ACTIVE_WATTS = 100
REGULATED_POWER_MIN_CHANGE_AMPS = 0.05
REGULATED_POWER_TARGET_DEADBAND_WATTS = 100
REGULATED_POWER_TARGET_DEADBAND_STEPS = 1


def _clamp(value: float, lower: float, upper: float) -> float:
    """Clamp a value to inclusive bounds."""
    return min(max(value, lower), upper)


def _current_bounds(
    data: Mapping[str, Any] | None, profile: KebaProfile
) -> tuple[float, float]:
    """Return the allowed current bounds in amps."""
    min_current = float(profile.charging_current_min_amps)
    return min_current, max(min_current, max_current_limit(data))


def _limited_current_change(change: float) -> float:
    """Limit a regulator change to the configured maximum step."""
    return _clamp(
        change,
        -REGULATED_POWER_MAX_CHANGE_AMPS,
        REGULATED_POWER_MAX_CHANGE_AMPS,
    )


def _round_to_current_step(value: float) -> float:
    """Round an amp value to the controller current step."""
    steps = round(value / REGULATED_POWER_CURRENT_STEP_AMPS)
    return steps * REGULATED_POWER_CURRENT_STEP_AMPS


def _target_deadband_watts(watts_per_amp: float) -> float:
    """Return the regulation deadband for the current phase configuration."""
    return max(
        REGULATED_POWER_TARGET_DEADBAND_WATTS,
        watts_per_amp
        * REGULATED_POWER_CURRENT_STEP_AMPS
        * REGULATED_POWER_TARGET_DEADBAND_STEPS,
    )


def max_current_limit(data: Mapping[str, Any] | None) -> float:
    """Return the effective upper current limit in amps."""
    if data is not None:
        limit = scale_milliamps(data.get(KEY_MAX_SUPPORTED_CURRENT))
        if limit is not None:
            return min(63.0, limit)

    return 63.0


def active_phase_count(
    data: Mapping[str, Any] | None,
    model_key: Optional[str],
) -> int:
    """Return the active phase count used for power/current conversion."""
    if model_key == MODEL_KEY_P40 and data is not None:
        phase_state = data.get(KEY_PHASE_SWITCH_STATE)
        if phase_state == 1:
            return 1
        if phase_state == 3:
            return 3

        raw_product = data.get(KEY_PRODUCT)
        if raw_product is not None:
            digits = str(abs(raw_product)).zfill(7)
            return 1 if digits[3] == "1" else 3

    return 3


def power_factor(data: Mapping[str, Any] | None) -> float:
    """Return the current power factor as a multiplier."""
    if data is None:
        return 1.0

    raw = data.get(KEY_POWER_FACTOR)
    if not isinstance(raw, int) or raw <= 0:
        return 1.0

    return min(1.0, raw / 1000)


def power_per_amp(
    data: Mapping[str, Any] | None,
    model_key: Optional[str],
    *,
    include_power_factor: bool = False,
) -> float:
    """Return watts per amp for the currently active phases."""
    phase_count = active_phase_count(data, model_key)

    if data is None:
        voltage_sum = phase_count * NOMINAL_PHASE_VOLTAGE
    else:
        voltages = [
            float(raw)
            for raw in (
                data.get(KEY_VOLTAGE_L1),
                data.get(KEY_VOLTAGE_L2),
                data.get(KEY_VOLTAGE_L3),
            )
            if isinstance(raw, int) and raw > 0
        ]

        if not voltages:
            voltage_sum = phase_count * NOMINAL_PHASE_VOLTAGE
        elif phase_count == 1:
            voltage_sum = sum(voltages) / len(voltages)
        elif len(voltages) >= phase_count:
            voltage_sum = sum(voltages[:phase_count])
        else:
            voltage_sum = sum(voltages) * phase_count / len(voltages)

    if include_power_factor:
        return voltage_sum * power_factor(data)

    return voltage_sum


def charging_power_max_value(
    data: Mapping[str, Any] | None,
    model_key: Optional[str],
    profile: KebaProfile,
) -> float:
    """Return the upper charging power bound in kW."""
    return round(max_current_limit(data) * power_per_amp(data, model_key) / 1000, 1)


def charging_power_current_raw(
    data: Mapping[str, Any] | None,
    model_key: Optional[str],
    profile: KebaProfile,
    target_kw: float,
) -> Optional[int]:
    """Return the direct current limit raw value for a charging power target."""
    if target_kw <= 0:
        return 0

    watts_per_amp = power_per_amp(data, model_key, include_power_factor=True)
    if watts_per_amp <= 0:
        return None

    target_current = target_kw * 1000 / watts_per_amp
    min_current, max_current = _current_bounds(data, profile)
    desired_current = _round_to_current_step(
        _clamp(target_current, min_current, max_current)
    )
    return int(round(desired_current * 1000))


def regulated_power_current_raw(
    data: Mapping[str, Any],
    model_key: Optional[str],
    profile: KebaProfile,
    target_kw: float,
) -> Optional[int]:
    """Return the next current limit raw value for active-power regulation."""
    if target_kw <= 0:
        return None

    watts_per_amp = power_per_amp(data, model_key, include_power_factor=True)
    if watts_per_amp <= 0:
        return None

    target_watts = target_kw * 1000
    current_limit = scale_milliamps(data.get(KEY_MAX_CHARGING_CURRENT))
    active_power = scale_milliwatts(data.get(KEY_ACTIVE_POWER))
    target_current = target_watts / watts_per_amp
    min_current, max_current = _current_bounds(data, profile)

    if current_limit is None:
        desired_current = target_current
    elif (
        active_power is None
        or active_power < REGULATED_POWER_MIN_ACTIVE_WATTS
        and current_limit <= 0
    ):
        desired_current = target_current
    elif active_power < REGULATED_POWER_MIN_ACTIVE_WATTS:
        desired_current = current_limit + _limited_current_change(
            target_current - current_limit
        )
    else:
        error_watts = target_watts - active_power
        if abs(error_watts) <= _target_deadband_watts(watts_per_amp):
            return None

        desired_current = current_limit + _limited_current_change(
            REGULATED_POWER_GAIN * error_watts / watts_per_amp
        )

    desired_current = _round_to_current_step(
        _clamp(desired_current, min_current, max_current)
    )

    if (
        current_limit is not None
        and abs(desired_current - current_limit) < REGULATED_POWER_MIN_CHANGE_AMPS
    ):
        return None

    return int(round(desired_current * 1000))


__all__ = [
    "charging_power_current_raw",
    "charging_power_max_value",
    "max_current_limit",
    "power_per_amp",
    "regulated_power_current_raw",
]
