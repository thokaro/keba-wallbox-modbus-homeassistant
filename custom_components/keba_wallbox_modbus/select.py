"""Select platform for KEBA Wallbox Modbus."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Optional

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import KebaDataUpdateCoordinator
from .entity import KebaEntity, async_add_description_entities
from .types import KebaConfigEntry
from .write_descriptions import KebaSelectDescription, SELECT_DESCRIPTIONS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEBA wallbox selects."""
    coordinator = entry.runtime_data
    async_add_description_entities(
        async_add_entities,
        coordinator,
        SELECT_DESCRIPTIONS,
        KebaSelectEntity,
    )


class KebaSelectEntity(KebaEntity, SelectEntity):
    """Representation of a KEBA select."""

    entity_description: KebaSelectDescription

    def __init__(
        self,
        coordinator: KebaDataUpdateCoordinator,
        description: KebaSelectDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_options = self._options()

    def _options(self) -> list[str]:
        """Return the active options."""
        if self.entity_description.options_fn is not None:
            return self.entity_description.options_fn(self.coordinator.profile)
        return list(self.entity_description.options)

    def _read_map(self) -> Mapping[int, str]:
        """Return the active read mapping."""
        if self.entity_description.read_map_fn is not None:
            return self.entity_description.read_map_fn(self.coordinator.profile)
        return self.entity_description.read_map

    def _write_map(self) -> Mapping[str, int]:
        """Return the active write mapping."""
        if self.entity_description.write_map_fn is not None:
            return self.entity_description.write_map_fn(self.coordinator.profile)
        return self.entity_description.write_map

    @property
    def current_option(self) -> Optional[str]:
        """Return the selected option."""
        raw = None if self.coordinator.data is None else self.coordinator.data.get(
            self.entity_description.read_key
        )
        if raw is None:
            return None
        return self._read_map().get(raw)

    async def async_select_option(self, option: str) -> None:
        """Write a new select option."""
        await self.coordinator.async_write_register_and_refresh(
            self.entity_description.register,
            self._write_map()[option],
        )
