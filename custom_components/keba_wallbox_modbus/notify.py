"""Support for KEBA notifications."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, UDP_DISPLAY_MAX_DURATION
from .coordinator import KebaDataUpdateCoordinator
from .entity import keba_device_info
from .modbus import KebaModbusError

LOGGER = logging.getLogger(__name__)

ATTR_MAX_TIME = "max_time"
ATTR_DATA = "data"
ATTR_MESSAGE = "message"
ATTR_MIN_TIME = "min_time"

SERVICE_DISPLAY_MESSAGE = "display_message"
DISPLAY_TIME_SCHEMA = vol.All(
    vol.Coerce(float),
    vol.Range(min=0, max=UDP_DISPLAY_MAX_DURATION),
)
DISPLAY_MESSAGE_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_MIN_TIME): DISPLAY_TIME_SCHEMA,
        vol.Optional(ATTR_MAX_TIME): DISPLAY_TIME_SCHEMA,
    }
)
DISPLAY_MESSAGE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_DATA): DISPLAY_MESSAGE_DATA_SCHEMA,
        vol.Optional(ATTR_MIN_TIME): DISPLAY_TIME_SCHEMA,
        vol.Optional(ATTR_MAX_TIME): DISPLAY_TIME_SCHEMA,
    }
)
DISPLAY_MESSAGE_SERVICE_DESCRIPTION = {
    "name": "Display message",
    "description": "Send a message to a KEBA wallbox display.",
    "fields": {
        ATTR_MESSAGE: {
            "name": "Message",
            "description": "Text shown on the wallbox display.",
            "required": True,
            "example": "PV charging active",
            "selector": {"text": {}},
        },
        ATTR_DATA: {
            "name": "Data",
            "description": (
                "Optional display timing data. Supported keys are min_time and "
                "max_time."
            ),
            "selector": {"object": {}},
        },
    },
}


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


class KebaNotificationEntity(NotifyEntity):
    """Notification entity for the KEBA display."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: KebaDataUpdateCoordinator) -> None:
        """Initialize the notification entity."""
        unique_root = coordinator.entry.unique_id or coordinator.entry.entry_id
        self._attr_unique_id = f"{unique_root}_display_notify"
        self._coordinator = coordinator
        self._service_domain: str | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Describe the backing KEBA wallbox."""
        return keba_device_info(self._coordinator)

    async def async_added_to_hass(self) -> None:
        """Register the display message service once the entity ID is known."""
        await super().async_added_to_hass()

        if self.entity_id is None:
            return

        self._service_domain = split_entity_id(self.entity_id)[1]
        if self.hass.services.has_service(
            self._service_domain,
            SERVICE_DISPLAY_MESSAGE,
        ):
            LOGGER.error(
                "Cannot register service %s.%s because it already exists",
                self._service_domain,
                SERVICE_DISPLAY_MESSAGE,
            )
            return

        self.hass.services.async_register(
            self._service_domain,
            SERVICE_DISPLAY_MESSAGE,
            self._async_handle_display_message_service,
            DISPLAY_MESSAGE_SERVICE_SCHEMA,
        )
        service.async_set_service_schema(
            self.hass,
            self._service_domain,
            SERVICE_DISPLAY_MESSAGE,
            DISPLAY_MESSAGE_SERVICE_DESCRIPTION,
        )
        self.async_on_remove(self._async_unregister_display_message_service)

    async def _async_handle_display_message_service(self, call: ServiceCall) -> None:
        """Handle the device-specific display message service."""
        display_data = call.data.get(ATTR_DATA, {})
        await self.async_display_message(
            call.data[ATTR_MESSAGE],
            min_time=call.data.get(ATTR_MIN_TIME, display_data.get(ATTR_MIN_TIME)),
            max_time=call.data.get(ATTR_MAX_TIME, display_data.get(ATTR_MAX_TIME)),
        )

    def _async_unregister_display_message_service(self) -> None:
        """Unregister the device-specific display message service."""
        if self._service_domain is None:
            return

        self.hass.services.async_remove(
            self._service_domain,
            SERVICE_DISPLAY_MESSAGE,
        )

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
            self._coordinator.display_min_time if min_time is None else min_time
        )
        effective_max_time = (
            self._coordinator.display_max_time if max_time is None else max_time
        )
        try:
            await self._coordinator.async_display_text(
                message,
                min_time=effective_min_time,
                max_time=effective_max_time,
            )
        except KebaModbusError as err:
            raise HomeAssistantError(str(err)) from err
