"""DataUpdateCoordinator for KEBA Wallbox Modbus."""

from __future__ import annotations

from datetime import timedelta
import json
import logging
import socket
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UDP_HOST,
    DISCOVERY_REGISTER_MAP,
    KEY_FIRMWARE_VERSION,
    KEY_PRODUCT,
    KEY_SERIAL_NUMBER,
    DOMAIN,
    UDP_DISPLAY_MAX_LENGTH,
    UDP_DISPLAY_PORT,
    KebaProfile,
    detect_wallbox_model,
    format_firmware_version,
    format_serial_number,
    get_wallbox_profile,
)
from .modbus import KebaModbusError, KebaModbusHub

LOGGER = logging.getLogger(__name__)


class KebaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate KEBA wallbox polling and writes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self._config = {**entry.data, **entry.options}
        self._display_udp_host = self._config.get(CONF_UDP_HOST) or self._config[CONF_HOST]
        self.hub = KebaModbusHub(
            host=self._config[CONF_HOST],
            port=self._config[CONF_PORT],
            timeout=self._config[CONF_TIMEOUT],
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
        if not isinstance(min_time, (int, float)) or not isinstance(
            max_time, (int, float)
        ):
            raise KebaModbusError("Display times must be numeric")

        if min_time < 0 or min_time > 65535 or max_time < 0 or max_time > 65535:
            raise KebaModbusError(
                "Display times must be between 0 and 65535 seconds"
            )

        normalized_text = text.replace(" ", "$")[:UDP_DISPLAY_MAX_LENGTH]
        command = (
            f"display 1 {int(round(min_time))} {int(round(max_time))} 0 {normalized_text}"
        )
        await self.hass.async_add_executor_job(self._send_udp_display_command, command)

    def _send_udp_display_command(self, command: str) -> None:
        """Send a single UDP display command to the wallbox."""
        try:
            payload = command.encode("ascii")
        except UnicodeEncodeError as err:
            raise KebaModbusError(
                "Display text must contain ASCII characters only"
            ) from err

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
                udp_socket.settimeout(self._config[CONF_TIMEOUT])
                udp_socket.bind(("0.0.0.0", UDP_DISPLAY_PORT))
                udp_socket.sendto(
                    payload,
                    (self._display_udp_host, UDP_DISPLAY_PORT),
                )
        except OSError as err:
            raise KebaModbusError(
                f"Failed to send UDP display command to {self._display_udp_host}:{UDP_DISPLAY_PORT}: {err}"
            ) from err

    def _probe_display_support(self) -> bool:
        """Probe report 1 via UDP and derive display support from the product string."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
                udp_socket.settimeout(self._config[CONF_TIMEOUT])
                udp_socket.bind(("0.0.0.0", UDP_DISPLAY_PORT))
                udp_socket.sendto(
                    b"report 1",
                    (self._config[CONF_HOST], UDP_DISPLAY_PORT),
                )
                payload, address = udp_socket.recvfrom(4096)
        except OSError as err:
            LOGGER.debug(
                "UDP display probe failed for %s:%s: %s",
                self._config[CONF_HOST],
                UDP_DISPLAY_PORT,
                err,
            )
            return False

        if address[0] != self._config[CONF_HOST]:
            LOGGER.debug(
                "Ignoring UDP display probe response from unexpected host %s for %s",
                address[0],
                self._config[CONF_HOST],
            )
            return False

        try:
            report_1 = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            LOGGER.debug(
                "Failed to decode UDP report 1 from %s: %s",
                self._config[CONF_HOST],
                err,
            )
            return False

        return _report_1_has_display(report_1)

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


def _report_1_has_display(report_1: dict[str, Any]) -> bool:
    """Determine display support like keba_kecontact.ChargingStationInfo."""
    if not isinstance(report_1, dict):
        return False

    if report_1.get("ID") != "1":
        return False

    product = report_1.get("Product")
    if not isinstance(product, str):
        return False

    p_split = product.split("-")
    if len(p_split) < 4:
        return False

    manufacturer = p_split[0]
    model = p_split[1]

    if manufacturer != "KC":
        return False

    if model != "P30":
        return False

    return "KC-P30-EC220112-000-DE" not in product
