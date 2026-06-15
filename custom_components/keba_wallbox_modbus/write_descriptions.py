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

from .decoding import scale_milliamps
from .profiles import KebaProfile
from .registers import (
    KEY_FAILSAFE_CURRENT,
    KEY_FAILSAFE_TIMEOUT,
    KEY_MAX_CHARGING_CURRENT,
    KEY_PHASE_SWITCH_SOURCE,
    KEY_PHASE_SWITCH_STATE,
    PHASE_SWITCH_STATE_MAP,
    PHASE_SWITCH_STATE_WRITE_MAP,
    WRITE_REGISTER_CHARGING_CURRENT,
    WRITE_REGISTER_FAILSAFE_CURRENT,
    WRITE_REGISTER_FAILSAFE_PERSIST,
    WRITE_REGISTER_FAILSAFE_TIMEOUT,
    WRITE_REGISTER_FAST_CHARGING,
    WRITE_REGISTER_PHASE_SWITCH_SOURCE,
    WRITE_REGISTER_PHASE_SWITCH_STATE,
    WRITE_REGISTER_SESSION_ENERGY_LIMIT,
    WRITE_REGISTER_UNLOCK_PLUG,
)
from .coordinator import KebaDataUpdateCoordinator
from .power_control import (
    charging_power_max_value,
    max_current_limit,
)

CHARGING_POWER_KEY = "charging_power"


def _is_integer_value(value: float) -> bool:
    return float(value).is_integer()


def _is_tenth_amp_value(value: float) -> bool:
    return (float(value) * 10).is_integer()


def _is_tenth_kw_value(value: float) -> bool:
    return (float(value) * 10).is_integer()


def _max_current_limit(coordinator: KebaDataUpdateCoordinator) -> float:
    return max_current_limit(coordinator.data)


def _charging_power_max_value(coordinator: KebaDataUpdateCoordinator) -> float:
    return charging_power_max_value(
        coordinator.data,
        coordinator.model_key,
        coordinator.profile,
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
        register=WRITE_REGISTER_UNLOCK_PLUG,
        value=0,
        is_supported=lambda coordinator: coordinator.capabilities.supports_unlock_plug,
    ),
    KebaButtonDescription(
        key="persist_failsafe_settings",
        name="Persist failsafe settings",
        icon="mdi:content-save-cog-outline",
        entity_category=EntityCategory.CONFIG,
        register=WRITE_REGISTER_FAILSAFE_PERSIST,
        value=1,
        is_supported=lambda coordinator: (
            coordinator.capabilities.supports_failsafe_persist
        ),
    ),
    KebaButtonDescription(
        key="activate_fast_charging",
        name="Activate fast charging",
        icon="mdi:flash",
        register=WRITE_REGISTER_FAST_CHARGING,
        value=1,
        is_supported=lambda coordinator: (
            coordinator.capabilities.supports_fast_charging
        ),
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
        register=WRITE_REGISTER_PHASE_SWITCH_SOURCE,
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
        options=list(PHASE_SWITCH_STATE_MAP.values()),
        register=WRITE_REGISTER_PHASE_SWITCH_STATE,
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
    from_raw_fn: Optional[Callable[[KebaDataUpdateCoordinator, int], float]] = None
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
        native_step=0.1,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.BOX,
        register=WRITE_REGISTER_CHARGING_CURRENT,
        to_raw_fn=lambda _, value: int(round(value * 1000)),
        read_key=KEY_MAX_CHARGING_CURRENT,
        from_raw_fn=lambda _, raw: scale_milliamps(raw) or 0.0,
        min_value_fn=lambda coordinator: float(
            coordinator.profile.charging_current_min_amps
        ),
        max_value_fn=_max_current_limit,
        validate_fn=lambda value: (
            None
            if _is_tenth_amp_value(value)
            else "Allowed values are 0.1 A steps"
        ),
        retain_last_value_on_zero_readback=True,
    ),
    KebaNumberDescription(
        key=CHARGING_POWER_KEY,
        name="Charging power",
        icon="mdi:home-lightning-bolt-outline",
        native_min_value=0,
        native_max_value=43.5,
        native_step=0.1,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        mode=NumberMode.BOX,
        register=WRITE_REGISTER_CHARGING_CURRENT,
        min_value_fn=lambda _: 0.0,
        max_value_fn=_charging_power_max_value,
        validate_fn=lambda value: (
            None
            if _is_tenth_kw_value(value)
            else "Allowed values are 0.1 kW steps"
        ),
        optimistic=True,
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
        register=WRITE_REGISTER_SESSION_ENERGY_LIMIT,
        to_raw_fn=lambda _, value: int(round(value * 100)),
        optimistic=True,
    ),
    KebaNumberDescription(
        key="failsafe_current",
        name="Failsafe current",
        icon="mdi:shield-alert-outline",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=32,
        native_step=0.1,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.SLIDER,
        register=WRITE_REGISTER_FAILSAFE_CURRENT,
        to_raw_fn=lambda _, value: int(round(value * 1000)),
        read_key=KEY_FAILSAFE_CURRENT,
        from_raw_fn=lambda _, raw: scale_milliamps(raw) or 0.0,
        validate_fn=lambda value: (
            None
            if _is_tenth_amp_value(value) and (value == 0 or 6 <= value <= 32)
            else "Allowed values are 0 A or 6-32 A in 0.1 A steps"
        ),
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
        register=WRITE_REGISTER_FAILSAFE_TIMEOUT,
        to_raw_fn=lambda _, value: int(round(value)),
        read_key=KEY_FAILSAFE_TIMEOUT,
        from_raw_fn=lambda _, raw: float(raw),
        validate_fn=lambda value: (
            None
            if _is_integer_value(value) and (value == 0 or 5 <= value <= 600)
            else "Allowed values are integer 0 s or integer 5-600 s"
        ),
    ),
)


__all__ = [
    "BUTTON_DESCRIPTIONS",
    "CHARGING_POWER_KEY",
    "KebaButtonDescription",
    "KebaNumberDescription",
    "KebaSelectDescription",
    "NUMBER_DESCRIPTIONS",
    "SELECT_DESCRIPTIONS",
]
