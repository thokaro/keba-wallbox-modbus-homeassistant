"""Button platform for KEBA Wallbox Modbus."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import KebaEntity, async_add_description_entities, get_entry_coordinator
from .write_descriptions import BUTTON_DESCRIPTIONS, KebaButtonDescription
from .coordinator import KebaDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEBA wallbox buttons."""
    coordinator = get_entry_coordinator(hass.data, entry.entry_id)
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
