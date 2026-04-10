"""Support for KEBA notifications."""

from __future__ import annotations

from typing import Any

from homeassistant.components.notify import ATTR_DATA, BaseNotificationService
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .coordinator import KebaDataUpdateCoordinator


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BaseNotificationService | None:
    """Return the notify service."""
    if discovery_info is None:
        return None

    coordinator: KebaDataUpdateCoordinator | None = hass.data[DOMAIN].get(
        discovery_info[ATTR_CONFIG_ENTRY_ID]
    )
    if coordinator is None:
        return None

    return KebaNotificationService(coordinator)


class KebaNotificationService(BaseNotificationService):
    """Notification service for the KEBA display."""

    def __init__(self, coordinator: KebaDataUpdateCoordinator) -> None:
        """Initialize the service."""
        self.entry_id = coordinator.entry.entry_id
        self._coordinator = coordinator

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send the message to the KEBA display."""
        try:
            data = kwargs.get(ATTR_DATA) or {}
            min_time = float(data.get("min_time", 2))
            max_time = float(data.get("max_time", 10))
            await self._coordinator.async_display_text(
                message,
                min_time=min_time,
                max_time=max_time,
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
