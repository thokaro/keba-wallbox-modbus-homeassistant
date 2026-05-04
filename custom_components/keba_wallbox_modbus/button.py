"""Button platform for KEBA Wallbox Modbus."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import KebaDataUpdateCoordinator
from .entity import KebaEntity, async_add_description_entities
from .types import KebaConfigEntry
from .write_descriptions import BUTTON_DESCRIPTIONS, KebaButtonDescription


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEBA wallbox buttons."""
    coordinator = entry.runtime_data
    async_add_description_entities(
        async_add_entities,
        coordinator,
        BUTTON_DESCRIPTIONS,
        KebaButtonEntity,
        is_supported=lambda current_coordinator, description: description.is_supported(
            current_coordinator
        ),
    )


class KebaButtonEntity(KebaEntity, ButtonEntity):
    """Representation of a KEBA wallbox action button."""

    entity_description: KebaButtonDescription

    def __init__(
        self,
        coordinator: KebaDataUpdateCoordinator,
        description: KebaButtonDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Trigger the action."""
        await self.coordinator.async_write_register_and_refresh(
            self.entity_description.register,
            self.entity_description.value,
        )
