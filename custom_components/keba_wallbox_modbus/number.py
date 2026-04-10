"""Number platform for KEBA Wallbox Modbus."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Optional

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    KEY_FAILSAFE_CURRENT,
    KEY_FAILSAFE_TIMEOUT,
    KEY_MAX_CHARGING_CURRENT,
    KEY_MAX_SUPPORTED_CURRENT,
    KEY_PHASE_SWITCH_STATE,
    KEY_PRODUCT,
    KEY_VOLTAGE_L1,
    KEY_VOLTAGE_L2,
    KEY_VOLTAGE_L3,
    MODEL_KEY_P40,
    scale_milliamps,
)
from .coordinator import KebaDataUpdateCoordinator
from .entity import KebaEntity

NOMINAL_PHASE_VOLTAGE = 230


def _format_value(value: float) -> str:
    """Format a numeric bound without noisy trailing decimals."""
    numeric = float(value)
    return f"{numeric:.0f}" if numeric.is_integer() else f"{numeric:.1f}"


def _max_current_limit(coordinator: KebaDataUpdateCoordinator) -> float:
    """Return the current register limit in amps."""
    if coordinator.data is not None:
        raw = coordinator.data.get(KEY_MAX_SUPPORTED_CURRENT)
        limit = scale_milliamps(raw)
        if limit is not None:
            return min(63.0, limit)

    return 63.0


def _default_phase_count(coordinator: KebaDataUpdateCoordinator) -> int:
    """Infer the nominal phase count from the product type when needed."""
    if coordinator.model_key != MODEL_KEY_P40 or coordinator.data is None:
        return 3

    raw_product = coordinator.data.get(KEY_PRODUCT)
    if raw_product is None:
        return 3

    digits = str(abs(raw_product)).zfill(7)
    return 1 if digits[3] == "1" else 3


def _active_phase_count(coordinator: KebaDataUpdateCoordinator) -> int:
    """Return the active phase count for current-to-power conversion."""
    if coordinator.data is not None:
        phase_state = coordinator.data.get(KEY_PHASE_SWITCH_STATE)
        if phase_state == 1:
            return 1
        if phase_state == 3:
            return 3

    return _default_phase_count(coordinator)


def _power_per_amp(coordinator: KebaDataUpdateCoordinator) -> int:
    """Return the current watts per amp for the active phase setup."""
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
    """Convert the current register value to a nominal kW limit."""
    amps = scale_milliamps(raw) or 0.0
    return round(amps * _power_per_amp(coordinator) / 1000, 1)


def _power_kw_to_current_raw(
    coordinator: KebaDataUpdateCoordinator,
    value: float,
) -> int:
    """Convert a nominal power target back to the current register."""
    amps = value * 1000 / _power_per_amp(coordinator)
    return int(round(amps * 1000))


def _charging_power_min_value(coordinator: KebaDataUpdateCoordinator) -> float:
    """Return the effective minimum charging power."""
    return round(
        coordinator.profile.charging_current_min_amps
        * _power_per_amp(coordinator)
        / 1000,
        1,
    )


def _charging_power_max_value(coordinator: KebaDataUpdateCoordinator) -> float:
    """Return the effective maximum charging power."""
    return round(
        _max_current_limit(coordinator) * _power_per_amp(coordinator) / 1000,
        1,
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
    optimistic: bool = False


NUMBER_DESCRIPTIONS: tuple[KebaNumberDescription, ...] = (
    KebaNumberDescription(
        key="charging_current_limit",
        name="Charging current limit",
        icon="mdi:current-ac",
        native_min_value=6,
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
    ),
    KebaNumberDescription(
        key="charging_power_limit",
        name="Charging power limit",
        icon="mdi:lightning-bolt",
        native_min_value=1.4,
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
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEBA wallbox numbers."""
    coordinator: KebaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        KebaNumberEntity(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
    )


class KebaNumberEntity(RestoreEntity, KebaEntity, NumberEntity):
    """Representation of a KEBA writable number."""

    entity_description: KebaNumberDescription

    def __init__(
        self,
        coordinator: KebaDataUpdateCoordinator,
        description: KebaNumberDescription,
    ) -> None:
        KebaEntity.__init__(self, coordinator, description.key)
        self.entity_description = description
        self._restored_value: Optional[float] = None

    async def async_added_to_hass(self) -> None:
        """Restore the last optimistic value if needed."""
        await super().async_added_to_hass()

        if not self.entity_description.optimistic:
            return

        state = await self.async_get_last_state()
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        try:
            self._restored_value = float(state.state)
        except ValueError:
            self._restored_value = None

    @property
    def native_value(self) -> Optional[float]:
        """Return the current value."""
        if (
            self.entity_description.read_key is not None
            and self.coordinator.data is not None
        ):
            raw = self.coordinator.data.get(self.entity_description.read_key)
            if raw is not None and self.entity_description.from_raw_fn is not None:
                return self.entity_description.from_raw_fn(self.coordinator, raw)

        return self._restored_value

    @property
    def native_min_value(self) -> float:
        """Return the effective minimum value."""
        if self.entity_description.min_value_fn is not None:
            return self.entity_description.min_value_fn(self.coordinator)

        return self.entity_description.native_min_value

    @property
    def native_max_value(self) -> float:
        """Return the effective maximum value."""
        if self.entity_description.max_value_fn is not None:
            dynamic_limit = self.entity_description.max_value_fn(self.coordinator)
        else:
            dynamic_limit = self.entity_description.native_max_value

        return max(self.native_min_value, dynamic_limit)

    async def async_set_native_value(self, value: float) -> None:
        """Write a new value to the wallbox."""
        if value < self.native_min_value:
            raise HomeAssistantError(
                f"Minimum allowed value is currently {_format_value(self.native_min_value)} "
                f"{self.native_unit_of_measurement}"
            )

        if value > self.native_max_value:
            raise HomeAssistantError(
                f"Maximum allowed value is currently {_format_value(self.native_max_value)} "
                f"{self.native_unit_of_measurement}"
            )

        await self.coordinator.async_write_register(
            self.entity_description.register,
            self.entity_description.to_raw_fn(self.coordinator, value),
        )
        self._restored_value = value
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
