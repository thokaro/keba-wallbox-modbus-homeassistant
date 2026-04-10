"""Select platform for KEBA Wallbox Modbus."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Optional

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    KebaProfile,
    KEY_PHASE_SWITCH_SOURCE,
    KEY_PHASE_SWITCH_STATE,
    PHASE_SWITCH_STATE_MAP,
    PHASE_SWITCH_STATE_WRITE_MAP,
)
from .coordinator import KebaDataUpdateCoordinator
from .entity import KebaEntity


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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEBA wallbox selects."""
    coordinator: KebaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        KebaSelectEntity(coordinator, description)
        for description in SELECT_DESCRIPTIONS
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
        await self.coordinator.async_write_register(
            self.entity_description.register,
            self._write_map()[option],
        )
        await self.coordinator.async_request_refresh()
