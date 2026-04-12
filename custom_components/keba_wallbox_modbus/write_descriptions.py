"""Central description metadata for writable KEBA entities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Optional

from homeassistant.components.button import ButtonEntityDescription
from homeassistant.components.number import NumberEntityDescription, NumberMode
from homeassistant.components.select import SelectEntityDescription
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.helpers.entity import EntityCategory

from .const import (
    KebaProfile,
    KEY_FAILSAFE_CURRENT,
    KEY_FAILSAFE_TIMEOUT,
    KEY_MAX_CHARGING_CURRENT,
    KEY_MAX_SUPPORTED_CURRENT,
    KEY_PHASE_SWITCH_SOURCE,
    KEY_PHASE_SWITCH_STATE,
    KEY_PRODUCT,
    KEY_VOLTAGE_L1,
    KEY_VOLTAGE_L2,
    KEY_VOLTAGE_L3,
    MODEL_KEY_P40,
    PHASE_SWITCH_STATE_MAP,
    PHASE_SWITCH_STATE_WRITE_MAP,
    scale_milliamps,
)
from .coordinator import KebaDataUpdateCoordinator

NOMINAL_PHASE_VOLTAGE = 230


def _is_integer_value(value: float) -> bool:
    return float(value).is_integer()


def _max_current_limit(coordinator: KebaDataUpdateCoordinator) -> float:
    if coordinator.data is not None:
        raw = coordinator.data.get(KEY_MAX_SUPPORTED_CURRENT)
        limit = scale_milliamps(raw)
        if limit is not None:
            return min(63.0, limit)

    return 63.0


def _default_phase_count(coordinator: KebaDataUpdateCoordinator) -> int:
    if coordinator.model_key != MODEL_KEY_P40 or coordinator.data is None:
        return 3

    raw_product = coordinator.data.get(KEY_PRODUCT)
    if raw_product is None:
        return 3

    digits = str(abs(raw_product)).zfill(7)
    return 1 if digits[3] == "1" else 3


def _active_phase_count(coordinator: KebaDataUpdateCoordinator) -> int:
    if coordinator.data is not None:
        phase_state = coordinator.data.get(KEY_PHASE_SWITCH_STATE)
        if phase_state == 1:
            return 1
        if phase_state == 3:
            return 3

    return _default_phase_count(coordinator)


def _power_per_amp(coordinator: KebaDataUpdateCoordinator) -> int:
    phase_count = _active_phase_count(coordinator)

    if coordinator.data is None:
        return phase_count * NOMINAL_PHASE_VOLTAGE

    voltages = [
        float(raw)
        for raw in (
            coordinator.data.get(KEY_VOLTAGE_L1),
            coordinator.data.get(KEY_VOLTAGE_L2),
            coordinator.data.get(KEY_VOLTAGE_L3),
        )
        if isinstance(raw, int) and raw > 0
    ]

    if not voltages:
        return phase_count * NOMINAL_PHASE_VOLTAGE

    if phase_count == 1:
        return round(sum(voltages) / len(voltages))

    if len(voltages) >= phase_count:
        return round(sum(voltages[:phase_count]))

    return round(sum(voltages) * phase_count / len(voltages))


def _current_raw_to_power_kw(
    coordinator: KebaDataUpdateCoordinator,
    raw: int,
) -> float:
    amps = scale_milliamps(raw) or 0.0
    return round(amps * _power_per_amp(coordinator) / 1000, 1)


def _power_kw_to_current_raw(
    coordinator: KebaDataUpdateCoordinator,
    value: float,
) -> int:
    amps = value * 1000 / _power_per_amp(coordinator)
    return int(round(amps * 1000))


def _charging_power_min_value(coordinator: KebaDataUpdateCoordinator) -> float:
    return round(
        coordinator.profile.charging_current_min_amps
        * _power_per_amp(coordinator)
        / 1000,
        1,
    )


def _charging_power_max_value(coordinator: KebaDataUpdateCoordinator) -> float:
    return round(
        _max_current_limit(coordinator) * _power_per_amp(coordinator) / 1000,
        1,
    )


@dataclass(frozen=True)
class KebaButtonDescription(ButtonEntityDescription):
    """Describe a KEBA button entity."""

    register: int = 0
    value: int = 0
    is_supported: Callable[[KebaDataUpdateCoordinator], bool] = field(
        default=lambda _: True
    )


BUTTON_DESCRIPTIONS: tuple[KebaButtonDescription, ...] = (
    KebaButtonDescription(
        key="unlock_plug",
        name="Unlock plug",
        icon="mdi:lock-open-variant-outline",
        register=5012,
        value=0,
        is_supported=lambda coordinator: coordinator.capabilities.supports_unlock_plug,
    ),
    KebaButtonDescription(
        key="persist_failsafe_settings",
        name="Persist failsafe settings",
        icon="mdi:content-save-cog-outline",
        entity_category=EntityCategory.CONFIG,
        register=5020,
        value=1,
        is_supported=lambda coordinator: coordinator.capabilities.supports_failsafe_persist,
    ),
    KebaButtonDescription(
        key="activate_fast_charging",
        name="Activate fast charging",
        icon="mdi:flash",
        register=5200,
        value=1,
        is_supported=lambda coordinator: coordinator.capabilities.supports_fast_charging,
    ),
)


@dataclass(frozen=True)
class KebaSelectDescription(SelectEntityDescription):
    """Describe a KEBA select entity."""

    register: int = 0
    read_key: str = ""
    read_map: Mapping[int, str] = field(default_factory=dict)
    write_map: Mapping[str, int] = field(default_factory=dict)
    options_fn: Optional[Callable[[KebaProfile], list[str]]] = None
    read_map_fn: Optional[Callable[[KebaProfile], Mapping[int, str]]] = None
    write_map_fn: Optional[Callable[[KebaProfile], Mapping[str, int]]] = None


SELECT_DESCRIPTIONS: tuple[KebaSelectDescription, ...] = (
    KebaSelectDescription(
        key="phase_switch_source",
        name="Phase switch source",
        icon="mdi:swap-horizontal-circle-outline",
        entity_category=EntityCategory.CONFIG,
        options=[],
        register=5050,
        read_key=KEY_PHASE_SWITCH_SOURCE,
        options_fn=lambda profile: list(profile.phase_switch_source_write_map),
        read_map_fn=lambda profile: profile.phase_switch_source_map,
        write_map_fn=lambda profile: profile.phase_switch_source_write_map,
    ),
    KebaSelectDescription(
        key="phase_switch_state",
        name="Phase switch state",
        icon="mdi:power-plug-battery",
        entity_category=EntityCategory.CONFIG,
        options=list(PHASE_SWITCH_STATE_WRITE_MAP),
        register=5052,
        read_key=KEY_PHASE_SWITCH_STATE,
        read_map=PHASE_SWITCH_STATE_MAP,
        write_map=PHASE_SWITCH_STATE_WRITE_MAP,
    ),
)


@dataclass(frozen=True)
class KebaNumberDescription(NumberEntityDescription):
    """Describe a KEBA writable number."""

    register: int = 0
    to_raw_fn: Callable[[KebaDataUpdateCoordinator, float], int] = field(
        default=lambda _, value: int(round(value))
    )
    read_key: Optional[str] = None
    from_raw_fn: Optional[
        Callable[[KebaDataUpdateCoordinator, int], float]
    ] = None
    min_value_fn: Optional[Callable[[KebaDataUpdateCoordinator], float]] = None
    max_value_fn: Optional[Callable[[KebaDataUpdateCoordinator], float]] = None
    validate_fn: Optional[Callable[[float], Optional[str]]] = None
    retain_last_value_on_zero_readback: bool = False
    optimistic: bool = False


NUMBER_DESCRIPTIONS: tuple[KebaNumberDescription, ...] = (
    KebaNumberDescription(
        key="charging_current_limit",
        name="Charging current limit",
        icon="mdi:current-ac",
        native_min_value=0,
        native_max_value=63,
        native_step=1,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.BOX,
        register=5004,
        to_raw_fn=lambda _, value: int(round(value * 1000)),
        read_key=KEY_MAX_CHARGING_CURRENT,
        from_raw_fn=lambda _, raw: scale_milliamps(raw) or 0.0,
        min_value_fn=lambda coordinator: float(
            coordinator.profile.charging_current_min_amps
        ),
        max_value_fn=_max_current_limit,
        retain_last_value_on_zero_readback=True,
    ),
    KebaNumberDescription(
        key="charging_power_limit",
        name="Charging power",
        icon="mdi:lightning-bolt",
        native_min_value=0,
        native_max_value=43.5,
        native_step=0.1,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        mode=NumberMode.SLIDER,
        register=5004,
        to_raw_fn=_power_kw_to_current_raw,
        read_key=KEY_MAX_CHARGING_CURRENT,
        from_raw_fn=_current_raw_to_power_kw,
        min_value_fn=_charging_power_min_value,
        max_value_fn=_charging_power_max_value,
        retain_last_value_on_zero_readback=True,
    ),
    KebaNumberDescription(
        key="session_energy_limit",
        name="Session energy limit",
        icon="mdi:battery-charging-high",
        native_min_value=0,
        native_max_value=655.35,
        native_step=0.01,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        mode=NumberMode.BOX,
        register=5010,
        to_raw_fn=lambda _, value: int(round(value * 100)),
        optimistic=True,
    ),
    KebaNumberDescription(
        key="failsafe_current",
        name="Failsafe current",
        icon="mdi:shield-bolt",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=32,
        native_step=1,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.SLIDER,
        register=5016,
        to_raw_fn=lambda _, value: int(round(value * 1000)),
        read_key=KEY_FAILSAFE_CURRENT,
        from_raw_fn=lambda _, raw: scale_milliamps(raw) or 0.0,
        validate_fn=lambda value: None
        if _is_integer_value(value) and (value == 0 or 6 <= value <= 32)
        else "Allowed values are integer 0 A or integer 6-32 A",
    ),
    KebaNumberDescription(
        key="failsafe_timeout",
        name="Failsafe timeout",
        icon="mdi:timer-cog-outline",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=600,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        register=5018,
        to_raw_fn=lambda _, value: int(round(value)),
        read_key=KEY_FAILSAFE_TIMEOUT,
        from_raw_fn=lambda _, raw: float(raw),
        validate_fn=lambda value: None
        if _is_integer_value(value) and (value == 0 or 5 <= value <= 600)
        else "Allowed values are integer 0 s or integer 5-600 s",
    ),
)


__all__ = [
    "BUTTON_DESCRIPTIONS",
    "KebaButtonDescription",
    "KebaNumberDescription",
    "KebaSelectDescription",
    "NUMBER_DESCRIPTIONS",
    "SELECT_DESCRIPTIONS",
]
