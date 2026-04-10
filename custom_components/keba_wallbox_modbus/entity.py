"""Shared entity helpers for KEBA Wallbox Modbus."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import KebaDataUpdateCoordinator


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
        unique_root = self.coordinator.entry.unique_id or self.coordinator.entry.entry_id
        return DeviceInfo(
            identifiers={(DOMAIN, unique_root)},
            manufacturer=MANUFACTURER,
            model=self.coordinator.model,
            name=self.coordinator.entry.title,
            serial_number=self.coordinator.device_serial,
            sw_version=self.coordinator.firmware_version,
        )
