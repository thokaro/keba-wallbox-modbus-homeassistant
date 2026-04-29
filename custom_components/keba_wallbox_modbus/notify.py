"""Support for KEBA notifications."""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import KebaDataUpdateCoordinator
from .entity import KebaEntity
from .modbus import KebaModbusError


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the KEBA display notify entity."""
    coordinator: KebaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if not await coordinator.async_probe_display_support():
        return

    async_add_entities([KebaNotificationEntity(coordinator)])


class KebaNotificationEntity(KebaEntity, NotifyEntity):
    """Notification entity for the KEBA display."""

    _attr_name = None

    def __init__(self, coordinator: KebaDataUpdateCoordinator) -> None:
        """Initialize the notification entity."""
        super().__init__(coordinator, "display_notify")

    async def async_send_message(
        self,
        message: str,
        title: str | None = None,
    ) -> None:
        """Send the message to the KEBA display."""
        await self._async_send_display_message(
            message,
            min_time=None,
            max_time=None,
        )
        self._async_record_notification()

    async def async_display_message(
        self,
        message: str,
        min_time: float | None = None,
        max_time: float | None = None,
    ) -> None:
        """Send the message to the KEBA display with custom duration."""
        await self._async_send_display_message(
            message,
            min_time=min_time,
            max_time=max_time,
        )
        self._async_record_notification()

    async def _async_send_display_message(
        self,
        message: str,
        *,
        min_time: float | None,
        max_time: float | None,
    ) -> None:
        """Send a message and translate device errors to Home Assistant errors."""
        effective_min_time = (
            self.coordinator.display_min_time if min_time is None else min_time
        )
        effective_max_time = (
            self.coordinator.display_max_time if max_time is None else max_time
        )
        try:
            await self.coordinator.async_display_text(
                message,
                min_time=effective_min_time,
                max_time=effective_max_time,
            )
        except KebaModbusError as err:
            raise HomeAssistantError(str(err)) from err
