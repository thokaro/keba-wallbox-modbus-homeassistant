"""DataUpdateCoordinator for KEBA Wallbox Modbus."""

from __future__ import annotations

from datetime import timedelta
from functools import partial
import logging
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .capabilities import KebaCapabilities, derive_capabilities
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UDP_HOST,
    CONF_UNIT_ID,
    DEFAULT_UNIT_ID,
    DISCOVERY_REGISTER_MAP,
    KEY_FIRMWARE_VERSION,
    KEY_PRODUCT,
    KEY_SERIAL_NUMBER,
    DOMAIN,
    KebaProfile,
    detect_wallbox_model,
    format_firmware_version,
    format_serial_number,
    get_wallbox_profile,
)
from .display import KebaDisplayClient
from .modbus import KebaModbusError, KebaModbusHub

LOGGER = logging.getLogger(__name__)


class KebaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate KEBA wallbox polling and writes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self._config = {**entry.data, **entry.options}
        self._display_udp_host = self._config.get(CONF_UDP_HOST) or self._config[CONF_HOST]
        self._display = KebaDisplayClient(
            host=self._display_udp_host,
            timeout=self._config[CONF_TIMEOUT],
        )
        self.hub = KebaModbusHub(
            host=self._config[CONF_HOST],
            port=self._config[CONF_PORT],
            timeout=self._config[CONF_TIMEOUT],
            unit_id=int(self._config.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)),
        )

        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=self._config[CONF_SCAN_INTERVAL]),
        )
        self._display_supported: Optional[bool] = None
        self._profile = get_wallbox_profile(None)

    @property
    def device_serial(self) -> Optional[str]:
        """Return the serial number as a string."""
        serial = None if self.data is None else self.data.get(KEY_SERIAL_NUMBER)
        return format_serial_number(serial) or self.entry.unique_id

    @property
    def model_key(self) -> Optional[str]:
        """Return the detected wallbox model key."""
        if self.data is None:
            return self._profile.model_key
        return detect_wallbox_model(self.data.get(KEY_PRODUCT))

    @property
    def model(self) -> str:
        """Return the detected wallbox model name."""
        return self._profile.model_name

    @property
    def profile(self) -> KebaProfile:
        """Return the detected wallbox profile."""
        return self._profile

    @property
    def capabilities(self) -> KebaCapabilities:
        """Return wallbox capabilities derived from product and profile data."""
        return derive_capabilities(
            product_raw=None if self.data is None else self.data.get(KEY_PRODUCT),
            model_key=self.model_key,
            profile=self._profile,
        )

    def _update_profile(self, data: dict[str, Any]) -> None:
        """Refresh the active profile from the current product register."""
        self._profile = get_wallbox_profile(detect_wallbox_model(data.get(KEY_PRODUCT)))

    @property
    def firmware_version_raw(self) -> Optional[int]:
        """Return the raw firmware register value."""
        return None if self.data is None else self.data.get(KEY_FIRMWARE_VERSION)

    @property
    def firmware_version(self) -> Optional[str]:
        """Return the formatted firmware version."""
        return format_firmware_version(
            self.firmware_version_raw,
            model_key=self.model_key,
        )

    @property
    def display_supported(self) -> bool:
        """Return whether the wallbox supports the UDP display command."""
        return self._display_supported is True

    async def async_shutdown(self) -> None:
        """Close resources held by the coordinator."""
        await self.hub.async_close()

    async def async_write_register(self, address: int, value: int) -> None:
        """Write a KEBA write register."""
        await self.hub.async_write_uint16(address, value)

    async def async_write_register_and_refresh(self, address: int, value: int) -> None:
        """Write a KEBA register and refresh coordinator data afterwards."""
        await self.async_write_register(address, value)
        await self.async_request_refresh()

    async def async_probe_display_support(self) -> bool:
        """Check display support using the same report-1 logic as the UDP integration."""
        if self._display_supported is not None:
            return self._display_supported

        self._display_supported = await self.hass.async_add_executor_job(
            self._probe_display_support
        )
        return self._display_supported

    async def async_display_text(
        self,
        text: str,
        min_time: float = 2,
        max_time: float = 10,
    ) -> None:
        """Show a transient text on the KEBA display via UDP."""
        await self.hass.async_add_executor_job(
            partial(
                self._display.send_text,
                text,
                min_time=min_time,
                max_time=max_time,
            )
        )

    def _probe_display_support(self) -> bool:
        """Probe report 1 via UDP and derive display support from the product string."""
        try:
            return self._display.probe_display_support()
        except KebaModbusError as err:
            LOGGER.debug(
                "UDP display probe failed for %s: %s",
                self._display_udp_host,
                err,
            )
            return False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data from the wallbox."""
        payload: dict[str, Any] = {}

        try:
            current = dict(self.data or {})
            if any(key not in current for key in DISCOVERY_REGISTER_MAP):
                payload.update(
                    await self.hub.async_read_named_registers(DISCOVERY_REGISTER_MAP)
                )

            detected = dict(current)
            detected.update(payload)
            self._update_profile(detected)

            missing_static = {
                key: address
                for key, address in self._profile.static_register_map.items()
                if key not in detected
            }
            if missing_static:
                payload.update(await self.hub.async_read_named_registers(missing_static))
                detected.update(payload)
                self._update_profile(detected)

            payload.update(
                await self.hub.async_read_named_registers(
                    self._profile.runtime_register_map,
                    optional_keys=self._profile.optional_runtime_keys,
                )
            )
        except KebaModbusError as err:
            raise UpdateFailed(str(err)) from err

        previous = dict(self.data or {})
        previous.update(payload)
        return previous
