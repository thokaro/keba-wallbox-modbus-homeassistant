"""Sensor platform for KEBA Wallbox Modbus."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import KebaDataUpdateCoordinator
from .entity import KebaEntity, async_add_description_entities, get_entry_coordinator
from .sensor_descriptions import (
    KebaSensorDescription,
    SENSOR_DESCRIPTIONS,
    is_supported_sensor,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEBA wallbox sensors."""
    coordinator = get_entry_coordinator(hass.data, entry.entry_id)
    async_add_description_entities(
        async_add_entities,
        coordinator,
        SENSOR_DESCRIPTIONS,
        KebaSensorEntity,
        is_supported=lambda current_coordinator, description: is_supported_sensor(
            description,
            current_coordinator.profile,
        ),
    )


class KebaSensorEntity(KebaEntity, SensorEntity):
    """Representation of a KEBA sensor."""

    entity_description: KebaSensorDescription

    def __init__(
        self,
        coordinator: KebaDataUpdateCoordinator,
        description: KebaSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        if description.options is not None:
            self._attr_options = list(description.options)

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""
        return self.entity_description.value_fn(
            self.coordinator,
            self.coordinator.data or {},
        )

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        """Return extra attributes for the sensor."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(
            self.coordinator,
            self.coordinator.data or {},
        )
