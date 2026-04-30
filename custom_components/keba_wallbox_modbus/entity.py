"""Shared entity helpers for KEBA Wallbox Modbus."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import KebaDataUpdateCoordinator

DescriptionT = TypeVar("DescriptionT")
EntityT = TypeVar("EntityT")


def keba_device_info(coordinator: KebaDataUpdateCoordinator) -> DeviceInfo:
    """Describe the backing KEBA wallbox."""
    unique_root = coordinator.entry.unique_id or coordinator.entry.entry_id
    return DeviceInfo(
        identifiers={(DOMAIN, unique_root)},
        manufacturer=MANUFACTURER,
        model=coordinator.model,
        name=coordinator.entry.title,
        serial_number=coordinator.device_serial,
        sw_version=coordinator.firmware_version,
    )


class KebaEntity(CoordinatorEntity[KebaDataUpdateCoordinator]):
    """Base class for KEBA entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KebaDataUpdateCoordinator, key: str) -> None:
        super().__init__(coordinator)
        unique_root = coordinator.entry.unique_id or coordinator.entry.entry_id
        self._attr_unique_id = f"{unique_root}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Describe the backing KEBA wallbox."""
        return keba_device_info(self.coordinator)


def async_add_description_entities(
    async_add_entities: AddEntitiesCallback,
    coordinator: KebaDataUpdateCoordinator,
    descriptions: Iterable[DescriptionT],
    entity_factory: Callable[[KebaDataUpdateCoordinator, DescriptionT], EntityT],
    *,
    is_supported: Callable[[KebaDataUpdateCoordinator, DescriptionT], bool] | None = None,
) -> None:
    """Instantiate description-driven entities with an optional support filter."""
    async_add_entities(
        entity_factory(coordinator, description)
        for description in descriptions
        if is_supported is None or is_supported(coordinator, description)
    )
