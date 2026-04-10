"""Low-level Modbus access helpers for KEBA wallboxes."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from time import monotonic
from typing import Any, Dict, Optional

from pymodbus.client import AsyncModbusTcpClient

from .const import (
    DISCOVERY_REGISTER_MAP,
    MIN_READ_INTERVAL,
    MIN_WRITE_INTERVAL,
    MODBUS_UNIT_ID,
)


class KebaModbusError(Exception):
    """Raised when Modbus communication with the wallbox fails."""


class KebaModbusHub:
    """Wrapper around pymodbus for KEBA specific access patterns."""

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._client: Optional[AsyncModbusTcpClient] = None
        self._lock = asyncio.Lock()
        self._last_write_at = 0.0
        self._unit_kwarg: Optional[str] = None

    async def async_close(self) -> None:
        """Close the TCP connection."""
        async with self._lock:
            self._reset_client()

    async def async_read_named_registers(
        self,
        registers: Mapping[str, int],
        *,
        optional_keys: frozenset[str] = frozenset(),
    ) -> Dict[str, Optional[int]]:
        """Read a sequence of UINT32 holding registers."""
        items = list(registers.items())
        values: Dict[str, Optional[int]] = {}
        successes = 0

        async with self._lock:
            client = await self._ensure_connected()

            for index, (key, address) in enumerate(items):
                try:
                    response = await self._async_call_with_unit_id(
                        client.read_holding_registers,
                        address=address,
                        count=2,
                    )
                except Exception as err:
                    if key in optional_keys:
                        values[key] = None
                    else:
                        self._reset_client()
                        raise KebaModbusError(
                            f"Failed to read register {address}: {err}"
                        ) from err
                else:
                    if response.isError() or len(response.registers) < 2:
                        if key in optional_keys:
                            values[key] = None
                        else:
                            self._reset_client()
                            raise KebaModbusError(
                                f"Modbus error while reading register {address}: {response}"
                            )
                    else:
                        successes += 1
                        values[key] = (response.registers[0] << 16) | response.registers[1]

                if index < len(items) - 1:
                    await asyncio.sleep(MIN_READ_INTERVAL)

        if successes == 0:
            raise KebaModbusError("No Modbus registers could be read")

        return values

    async def async_write_uint16(self, address: int, value: int) -> None:
        """Write a UINT16 holding register."""
        async with self._lock:
            await self._respect_write_interval()
            client = await self._ensure_connected()

            try:
                response = await self._async_call_with_unit_id(
                    client.write_register,
                    address=address,
                    value=value,
                )
            except Exception as err:
                self._reset_client()
                raise KebaModbusError(
                    f"Failed to write register {address}: {err}"
                ) from err

            if response.isError():
                raise KebaModbusError(
                    f"Modbus error while writing register {address}: {response}"
                )

            self._last_write_at = monotonic()

    async def _ensure_connected(self) -> AsyncModbusTcpClient:
        """Return a connected Modbus TCP client."""
        client = self._get_client()
        if client.connected:
            return client

        try:
            await client.connect()
        except Exception as err:
            self._reset_client()
            raise KebaModbusError(
                f"Could not connect to the wallbox at {self._host}:{self._port}: {err}"
            ) from err

        if not client.connected:
            self._reset_client()
            raise KebaModbusError(
                f"Could not connect to the wallbox at {self._host}:{self._port}"
            )

        return client

    async def _async_call_with_unit_id(self, method: Any, **kwargs: Any) -> Any:
        """Call a pymodbus method using the supported unit-id keyword."""
        if self._unit_kwarg is not None:
            return await method(**kwargs, **{self._unit_kwarg: MODBUS_UNIT_ID})

        for keyword in ("slave", "device_id"):
            try:
                response = await method(**kwargs, **{keyword: MODBUS_UNIT_ID})
            except TypeError as err:
                if "unexpected keyword" not in str(err):
                    raise
            else:
                self._unit_kwarg = keyword
                return response

        raise TypeError("The installed pymodbus version does not support slave/device_id")

    def _get_client(self) -> AsyncModbusTcpClient:
        """Create the pymodbus client on demand."""
        if self._client is None:
            self._client = AsyncModbusTcpClient(
                host=self._host,
                port=self._port,
                timeout=self._timeout,
            )
        return self._client

    def _reset_client(self) -> None:
        """Dispose the underlying client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    async def _respect_write_interval(self) -> None:
        """Keep writes within KEBA's recommended interval."""
        remaining = MIN_WRITE_INTERVAL - (monotonic() - self._last_write_at)
        if remaining > 0:
            await asyncio.sleep(remaining)


async def async_probe_device(host: str, port: int, timeout: int) -> Dict[str, Optional[int]]:
    """Probe the wallbox and return its static identifiers."""
    hub = KebaModbusHub(host, port, timeout)
    try:
        return await hub.async_read_named_registers(DISCOVERY_REGISTER_MAP)
    finally:
        await hub.async_close()
