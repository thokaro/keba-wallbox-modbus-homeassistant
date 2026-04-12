"""Number platform for KEBA Wallbox Modbus."""

from __future__ import annotations

from typing import Optional

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.exceptions import HomeAssistantError

from .coordinator import KebaDataUpdateCoordinator
from .entity import KebaEntity, async_add_description_entities, get_entry_coordinator
from .write_descriptions import KebaNumberDescription, NUMBER_DESCRIPTIONS


def _format_value(value: float) -> str:
    """Format a numeric bound without noisy trailing decimals."""
    numeric = float(value)
    return f"{numeric:.0f}" if numeric.is_integer() else f"{numeric:.1f}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEBA wallbox numbers."""
    coordinator = get_entry_coordinator(hass.data, entry.entry_id)
    async_add_description_entities(
        async_add_entities,
        coordinator,
        NUMBER_DESCRIPTIONS,
        KebaNumberEntity,
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
        self._restored_native_value: Optional[float] = None
        self._cached_native_value: Optional[float] = None

    async def async_added_to_hass(self) -> None:
        """Restore the last relevant value if needed."""
        await super().async_added_to_hass()

        if not (
            self.entity_description.optimistic
            or self.entity_description.retain_last_value_on_zero_readback
        ):
            return

        state = await self.async_get_last_state()
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        try:
            self._restored_native_value = float(state.state)
        except ValueError:
            self._restored_native_value = None

    def _fallback_native_value(self) -> Optional[float]:
        """Return the best local fallback value."""
        if self._cached_native_value is not None:
            return self._cached_native_value
        return self._restored_native_value

    @property
    def native_value(self) -> Optional[float]:
        """Return the current value."""
        if (
            self.entity_description.read_key is not None
            and self.coordinator.data is not None
        ):
            raw = self.coordinator.data.get(self.entity_description.read_key)
            if raw is not None and self.entity_description.from_raw_fn is not None:
                if (
                    self.entity_description.retain_last_value_on_zero_readback
                    and raw == 0
                ):
                    return self._fallback_native_value()

                value = self.entity_description.from_raw_fn(self.coordinator, raw)
                self._cached_native_value = value
                return value

        return self._fallback_native_value()

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
        if self.entity_description.validate_fn is not None:
            validation_error = self.entity_description.validate_fn(value)
            if validation_error is not None:
                raise HomeAssistantError(validation_error)

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

        await self.coordinator.async_write_register_and_refresh(
            self.entity_description.register,
            self.entity_description.to_raw_fn(self.coordinator, value),
        )
        self._cached_native_value = value
        self.async_write_ha_state()
