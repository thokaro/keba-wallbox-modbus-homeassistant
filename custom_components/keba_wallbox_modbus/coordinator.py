"""DataUpdateCoordinator for KEBA Wallbox Modbus."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import timedelta
from functools import partial
import logging
from time import monotonic
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .capabilities import KebaCapabilities, derive_capabilities
from .config_data import effective_config
from .const import (
    CONF_DISPLAY_MAX_TIME,
    CONF_DISPLAY_MIN_TIME,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UDP_HOST,
    CONF_UNIT_ID,
    DEFAULT_DISPLAY_MAX_TIME,
    DEFAULT_DISPLAY_MIN_TIME,
    DEFAULT_UNIT_ID,
    DOMAIN,
    SLOW_RUNTIME_POLL_INTERVAL,
    WRITE_ASSUMPTION_TTL,
    WRITE_READBACK_RETRY_DELAY,
)
from .decoding import format_firmware_version, format_serial_number
from .display import KebaDisplayClient
from .modbus import KebaModbusError, KebaModbusHub
from .power_control import charging_power_current_raw, regulated_power_current_raw
from .profiles import KebaProfile, detect_wallbox_model, get_wallbox_profile
from .registers import (
    DISCOVERY_REGISTER_MAP,
    KEY_FIRMWARE_VERSION,
    KEY_MAX_CHARGING_CURRENT,
    KEY_PRODUCT,
    KEY_SERIAL_NUMBER,
    WRITE_REGISTER_CHARGING_CURRENT,
)

LOGGER = logging.getLogger(__name__)

CHARGING_POWER_TARGET_REGULATION_HOLDOFF_CYCLES = 2


class KebaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate KEBA wallbox polling and writes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self._config = effective_config(dict(entry.data), dict(entry.options))
        self._display_udp_host = (
            self._config.get(CONF_UDP_HOST) or self._config[CONF_HOST]
        )
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
        self._charging_power_target: Optional[float] = None
        self._charging_current_regulation_enabled = False
        self._charging_current_regulation_holdoff_cycles = 0
        self._last_slow_runtime_poll_at: Optional[float] = None
        self._write_intent_counter = 0
        self._write_intents: dict[int, int] = {}
        self._pending_assumed_values: dict[str, tuple[Any, float]] = {}

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

    def _runtime_registers_for_poll(
        self,
        current: dict[str, Any],
    ) -> tuple[dict[str, int], bool]:
        """Return runtime registers for the next polling pass."""
        slow_registers = self._profile.slow_runtime_register_map
        fast_registers = self._profile.fast_runtime_register_map

        now = monotonic()
        slow_due = (
            any(key not in current for key in slow_registers)
            or self._last_slow_runtime_poll_at is None
            or now - self._last_slow_runtime_poll_at >= SLOW_RUNTIME_POLL_INTERVAL
        )
        if slow_due:
            return {**fast_registers, **slow_registers}, True

        return fast_registers, False

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
    def display_min_time(self) -> float:
        """Return the default minimum display duration."""
        return float(self._config.get(CONF_DISPLAY_MIN_TIME, DEFAULT_DISPLAY_MIN_TIME))

    @property
    def display_max_time(self) -> float:
        """Return the default maximum display duration."""
        return float(self._config.get(CONF_DISPLAY_MAX_TIME, DEFAULT_DISPLAY_MAX_TIME))

    @property
    def charging_power_target(self) -> Optional[float]:
        """Return the charging power target in kW."""
        return self._charging_power_target

    @property
    def charging_current_regulation_enabled(self) -> bool:
        """Return whether charging current regulation is enabled."""
        return self._charging_current_regulation_enabled

    def set_charging_power_target(self, value: Optional[float]) -> None:
        """Set the charging power target in kW."""
        if value is None or value <= 0:
            self._charging_power_target = None
            return

        self._charging_power_target = value

    def set_charging_current_regulation_enabled(self, enabled: bool) -> None:
        """Enable or disable charging current regulation."""
        self._charging_current_regulation_enabled = enabled

    def assume_register_values(self, values: dict[str, Any]) -> None:
        """Publish locally known register values before the next Modbus readback."""
        if not values:
            return

        if not hasattr(self, "_pending_assumed_values"):
            self._pending_assumed_values = {}
        deadline = monotonic() + WRITE_ASSUMPTION_TTL
        for key, value in values.items():
            self._pending_assumed_values[key] = (value, deadline)

        self._publish_register_payload(values, protect_pending=False)

    def _apply_pending_assumed_values(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Keep recent write assumptions until the wallbox confirms or they expire."""
        pending = getattr(self, "_pending_assumed_values", {})
        if not pending:
            return payload

        now = monotonic()
        filtered = dict(payload)
        for key, (expected, deadline) in list(pending.items()):
            if now >= deadline:
                pending.pop(key, None)
                continue

            if key not in filtered:
                continue

            if filtered[key] == expected:
                pending.pop(key, None)
            else:
                filtered[key] = expected

        return filtered

    def _publish_register_payload(
        self,
        payload: dict[str, Any],
        *,
        protect_pending: bool = True,
    ) -> None:
        """Merge register values into coordinator data and notify listeners."""
        values = self._apply_pending_assumed_values(payload) if protect_pending else payload
        data = dict(self.data or {})
        data.update(values)
        self._update_profile(data)
        self.async_set_updated_data(data)

    @staticmethod
    def _readback_matches_expected(
        payload: dict[str, Any],
        expected_values: dict[str, Any] | None,
    ) -> bool:
        """Return whether a readback confirms the expected values."""
        return expected_values is None or all(
            payload.get(key) == value for key, value in expected_values.items()
        )

    async def async_shutdown(self) -> None:
        """Close resources held by the coordinator."""
        await self.hub.async_close()

    async def async_write_register(self, address: int, value: int) -> None:
        """Write a KEBA write register."""
        await self.hub.async_write_uint16(address, value)

    def _write_intent_token(self, address: int) -> int:
        """Mark a write as the latest intent for one register address."""
        self._write_intent_counter = getattr(self, "_write_intent_counter", 0) + 1
        if not hasattr(self, "_write_intents"):
            self._write_intents = {}
        self._write_intents[address] = self._write_intent_counter
        return self._write_intent_counter

    def _is_latest_write_intent(self, address: int, token: int) -> bool:
        """Return whether a write intent is still current."""
        return getattr(self, "_write_intents", {}).get(address) == token

    def _clear_write_intent(self, address: int, token: int) -> None:
        """Clear a completed write intent if it is still current."""
        if self._is_latest_write_intent(address, token):
            self._write_intents.pop(address, None)

    async def _async_read_register_keys(
        self,
        keys: Iterable[str],
    ) -> dict[str, Any] | None:
        """Read selected register keys without publishing coordinator data."""
        register_map = {
            **self._profile.static_register_map,
            **self._profile.runtime_register_map,
        }
        registers = {key: register_map[key] for key in keys if key in register_map}
        if not registers:
            return None

        try:
            return await self.hub.async_read_named_registers(
                registers,
                optional_keys=frozenset(
                    key for key in registers if key in self._profile.optional_runtime_keys
                ),
            )
        except KebaModbusError as err:
            LOGGER.debug("Targeted register refresh failed: %s", err)
            return None

    async def async_refresh_register_keys(self, keys: Iterable[str]) -> None:
        """Refresh selected register keys and publish updated coordinator data."""
        await self._async_read_and_publish_register_keys(keys)

    async def _async_read_and_publish_register_keys(
        self,
        keys: Iterable[str],
        *,
        expected_values: dict[str, Any] | None = None,
    ) -> bool | None:
        """Read selected keys and publish them when the readback is usable."""
        payload = await self._async_read_register_keys(keys)
        if payload is None:
            await self.async_request_refresh()
            return None

        if not self._readback_matches_expected(payload, expected_values):
            LOGGER.debug(
                "Keeping assumed write values because readback is not updated yet: %s",
                payload,
            )
            return False

        self._publish_register_payload(payload)
        return True

    async def _async_refresh_after_write(
        self,
        address: int,
        token: int,
        refresh_keys: tuple[str, ...] | None,
        delay: float,
        expected_values: dict[str, Any] | None,
    ) -> None:
        """Refresh coordinator data after a completed write."""
        try:
            if delay > 0:
                await asyncio.sleep(delay)

            if not self._is_latest_write_intent(address, token):
                return

            if refresh_keys is None:
                await self.async_request_refresh()
                return

            readback_published = await self._async_read_and_publish_register_keys(
                refresh_keys,
                expected_values=expected_values,
            )
            if readback_published is False:
                await asyncio.sleep(WRITE_READBACK_RETRY_DELAY)
                if not self._is_latest_write_intent(address, token):
                    return

                await self._async_read_and_publish_register_keys(refresh_keys)
        finally:
            self._clear_write_intent(address, token)

    async def async_write_register_and_refresh(
        self,
        address: int,
        value: int,
        *,
        refresh_keys: Iterable[str] | None = None,
        assume_values: dict[str, Any] | None = None,
        refresh: bool = True,
        refresh_delay: float = 0,
        background_refresh: bool = False,
        refresh_name: str | None = None,
    ) -> bool:
        """Write a KEBA register and run the latest write's follow-up work."""
        token = self._write_intent_token(address)
        await self.async_write_register(address, value)
        if not self._is_latest_write_intent(address, token):
            return False

        if assume_values is not None:
            self.assume_register_values(assume_values)

        if not refresh:
            self._clear_write_intent(address, token)
            return True

        normalized_refresh_keys = (
            None if refresh_keys is None else tuple(refresh_keys)
        )
        refresh_target = self._async_refresh_after_write(
            address,
            token,
            normalized_refresh_keys,
            refresh_delay,
            assume_values,
        )
        if background_refresh:
            self.hass.async_create_task(
                refresh_target,
                name=refresh_name or f"keba_wallbox_modbus refresh after {address} write",
            )
        else:
            await refresh_target

        return True

    async def async_apply_charging_power_target(
        self,
        target_kw: float,
        data: dict[str, Any] | None = None,
        *,
        assume_readback: bool = False,
        refresh_readback: bool = False,
        refresh_delay: float = 0,
        background_refresh: bool = False,
        refresh_name: str | None = None,
    ) -> Optional[int]:
        """Apply the direct current limit for a charging power target."""
        source = data if data is not None else self.data

        raw = charging_power_current_raw(
            source,
            detect_wallbox_model(source.get(KEY_PRODUCT)) if source is not None else None,
            self._profile,
            target_kw,
        )
        if raw is None:
            return None

        LOGGER.debug("Applying charging power target %.2f kW as %s mA", target_kw, raw)
        applied = await self.async_write_register_and_refresh(
            WRITE_REGISTER_CHARGING_CURRENT,
            raw,
            assume_values=(
                {KEY_MAX_CHARGING_CURRENT: raw} if assume_readback else None
            ),
            refresh=refresh_readback,
            refresh_keys=(KEY_MAX_CHARGING_CURRENT,),
            refresh_delay=refresh_delay,
            background_refresh=background_refresh,
            refresh_name=refresh_name,
        )
        if not applied:
            return None

        if source is not None:
            source[KEY_MAX_CHARGING_CURRENT] = raw
        if self._charging_current_regulation_enabled:
            self._charging_current_regulation_holdoff_cycles = (
                CHARGING_POWER_TARGET_REGULATION_HOLDOFF_CYCLES
            )
        return raw

    async def async_apply_charging_current_regulation(
        self,
        data: dict[str, Any] | None = None,
    ) -> Optional[int]:
        """Apply one charging current regulation step and return the written raw value."""
        if not self._charging_current_regulation_enabled:
            return None

        target = self._charging_power_target
        if target is None:
            return None

        if self._charging_current_regulation_holdoff_cycles > 0:
            self._charging_current_regulation_holdoff_cycles -= 1
            LOGGER.debug(
                "Skipping charging current regulation after target update; %s holdoff cycles left",
                self._charging_current_regulation_holdoff_cycles,
            )
            return None

        source = data if data is not None else self.data
        if source is None:
            return None

        raw = regulated_power_current_raw(
            source,
            detect_wallbox_model(source.get(KEY_PRODUCT)),
            self._profile,
            target,
        )
        if raw is None:
            return None

        LOGGER.debug(
            "Applying charging current regulation for %.2f kW target as %s mA",
            target,
            raw,
        )
        applied = await self.async_write_register_and_refresh(
            WRITE_REGISTER_CHARGING_CURRENT,
            raw,
            refresh=False,
        )
        if not applied:
            return None

        source[KEY_MAX_CHARGING_CURRENT] = raw
        return raw

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
                payload.update(
                    await self.hub.async_read_named_registers(missing_static)
                )
                detected.update(payload)
                self._update_profile(detected)

            runtime_registers, slow_polled = self._runtime_registers_for_poll(detected)
            payload.update(
                await self.hub.async_read_named_registers(
                    runtime_registers,
                    optional_keys=self._profile.optional_runtime_keys,
                )
            )
            if slow_polled:
                self._last_slow_runtime_poll_at = monotonic()
        except KebaModbusError as err:
            raise UpdateFailed(str(err)) from err

        previous = dict(self.data or {})
        previous.update(self._apply_pending_assumed_values(payload))
        try:
            await self.async_apply_charging_current_regulation(previous)
        except KebaModbusError as err:
            LOGGER.debug("Charging current regulation update failed: %s", err)
        return previous
