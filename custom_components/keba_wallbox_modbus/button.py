"""Button platform for KEBA Wallbox Modbus."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KebaProfile
from .coordinator import KebaDataUpdateCoordinator
from .entity import KebaEntity


@dataclass(frozen=True)
class KebaButtonDescription(ButtonEntityDescription):
    """Describe a KEBA button entity."""

    register: int = 0
    value: int = 0
    is_supported: Callable[[KebaProfile], bool] = field(default=lambda _: True)


BUTTON_DESCRIPTIONS: tuple[KebaButtonDescription, ...] = (
    KebaButtonDescription(
        key="unlock_plug",
        name="Unlock plug",
        icon="mdi:lock-open-variant-outline",
        register=5012,
        value=0,
    ),
    KebaButtonDescription(
        key="persist_failsafe_settings",
        name="Persist failsafe settings",
        icon="mdi:content-save-cog-outline",
        entity_category=EntityCategory.CONFIG,
        register=5020,
        value=1,
        is_supported=lambda profile: profile.supports_failsafe_persist,
    ),
    KebaButtonDescription(
        key="activate_fast_charging",
        name="Activate fast charging",
        icon="mdi:flash",
        register=5200,
        value=1,
        is_supported=lambda profile: profile.supports_fast_charging,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEBA wallbox buttons."""
    coordinator: KebaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        KebaButtonEntity(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
        if description.is_supported(coordinator.profile)
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
        await self.coordinator.async_write_register(
            self.entity_description.register,
            self.entity_description.value,
        )
        await self.coordinator.async_request_refresh()
