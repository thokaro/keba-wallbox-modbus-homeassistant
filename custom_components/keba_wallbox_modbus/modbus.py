"""Low-level Modbus access helpers for KEBA wallboxes."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Dict, Optional

from pymodbus.client import AsyncModbusTcpClient

from .const import (
    MIN_READ_INTERVAL,
    MIN_WRITE_INTERVAL,
)
from .registers import DISCOVERY_REGISTER_MAP


class KebaModbusError(Exception):
    """Raised when Modbus communication with the wallbox fails."""


@dataclass
class _QueuedWrite:
    """Pending write state for one register address."""

    value: int
    waiters: list[asyncio.Future[None]] = field(default_factory=list)


class KebaModbusHub:
    """Wrapper around pymodbus for KEBA specific access patterns."""

    def __init__(self, host: str, port: int, timeout: int, unit_id: int) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._unit_id = unit_id
        self._client: Optional[AsyncModbusTcpClient] = None
        self._lock = asyncio.Lock()
        self._last_write_at: Optional[float] = None
        self._pending_writes: dict[int, _QueuedWrite] = {}
        self._write_queue_lock = asyncio.Lock()
        self._write_worker_task: Optional[asyncio.Task[None]] = None
        self._unit_kwarg: Optional[str] = None

    async def async_close(self) -> None:
        """Close the TCP connection."""
        if self._write_worker_task is not None:
            self._write_worker_task.cancel()
            try:
                await self._write_worker_task
            except asyncio.CancelledError:
                pass

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

        for index, (key, address) in enumerate(items):
            try:
                async with self._lock:
                    client = await self._ensure_connected()
                    response = await self._async_call_with_unit_id(
                        client.read_holding_registers,
                        address=address,
                        count=2,
                    )
            except Exception as err:
                if key in optional_keys:
                    values[key] = None
                else:
                    async with self._lock:
                        self._reset_client()
                    raise KebaModbusError(
                        f"Failed to read register {address}: {err}"
                    ) from err
            else:
                if response.isError() or len(response.registers) < 2:
                    if key in optional_keys:
                        values[key] = None
                    else:
                        async with self._lock:
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
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[None] = loop.create_future()
        async with self._write_queue_lock:
            queued = self._pending_writes.get(address)
            if queued is None:
                self._pending_writes[address] = _QueuedWrite(value, [waiter])
            else:
                queued.value = value
                queued.waiters.append(waiter)

            if self._write_worker_task is None or self._write_worker_task.done():
                self._write_worker_task = loop.create_task(
                    self._async_write_worker(),
                    name="keba_wallbox_modbus write worker",
                )

        await waiter

    async def _async_write_worker(self) -> None:
        """Process pending writes, coalescing repeated writes per register."""
        current_waiters: list[asyncio.Future[None]] = []
        try:
            while True:
                async with self._write_queue_lock:
                    if not self._pending_writes:
                        self._write_worker_task = None
                        return
                    address = next(iter(self._pending_writes))

                await self._respect_write_interval()

                async with self._write_queue_lock:
                    queued = self._pending_writes.pop(address, None)
                    if queued is None:
                        continue
                    value = queued.value
                    current_waiters = queued.waiters

                try:
                    await self._async_write_uint16_now(address, value)
                except Exception as err:
                    for waiter in current_waiters:
                        if not waiter.done():
                            waiter.set_exception(err)
                else:
                    for waiter in current_waiters:
                        if not waiter.done():
                            waiter.set_result(None)
                finally:
                    current_waiters = []
        except asyncio.CancelledError:
            for waiter in current_waiters:
                if not waiter.done():
                    waiter.cancel()
            async with self._write_queue_lock:
                for queued in self._pending_writes.values():
                    for waiter in queued.waiters:
                        if not waiter.done():
                            waiter.cancel()
                self._pending_writes.clear()
                self._write_worker_task = None
            raise

    async def _async_write_uint16_now(self, address: int, value: int) -> None:
        """Write a UINT16 holding register immediately."""
        async with self._lock:
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
            return await method(**kwargs, **{self._unit_kwarg: self._unit_id})

        for keyword in ("slave", "device_id"):
            try:
                response = await method(**kwargs, **{keyword: self._unit_id})
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
        if self._last_write_at is None:
            return

        remaining = MIN_WRITE_INTERVAL - (monotonic() - self._last_write_at)
        if remaining > 0:
            await asyncio.sleep(remaining)


async def async_probe_device(
    host: str,
    port: int,
    timeout: int,
    unit_id: int,
) -> Dict[str, Optional[int]]:
    """Probe the wallbox and return its static identifiers."""
    hub = KebaModbusHub(host, port, timeout, unit_id)
    try:
        return await hub.async_read_named_registers(DISCOVERY_REGISTER_MAP)
    finally:
        await hub.async_close()
