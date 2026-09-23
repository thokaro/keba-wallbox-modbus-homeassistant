"""Low-level Modbus access helpers for KEBA wallboxes."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from time import monotonic
from typing import Dict, Optional

from modbus_connection import ModbusError, ModbusProtocolError, ModbusUnit

MIN_READ_INTERVAL = 0.6
MIN_WRITE_INTERVAL = 5.0


class KebaModbusError(Exception):
    """Raised when Modbus communication with the wallbox fails."""


@dataclass
class _QueuedWrite:
    """Pending write state for one register address."""

    value: int
    waiters: list[asyncio.Future[None]] = field(default_factory=list)


class KebaModbusHub:
    """Backend-neutral KEBA device access, with throttled and coalesced writes."""

    def __init__(self, unit: ModbusUnit, *, timeout: float = 5) -> None:
        self._unit = unit
        # HA 2026.9 ships modbus-connection 4.10, before unit timeout
        # requirements were introduced. Bound the whole operation there;
        # newer backends resolve the timeout with other connection consumers.
        self._request_timeout: float | None = timeout
        if require_timeout := getattr(unit, "require_timeout", None):
            require_timeout(timeout)
            self._request_timeout = None
        # Enforced by the shared connection, including between polling cycles
        # and requests made by other consumers of this unit.
        self._unit.set_message_spacing(MIN_READ_INTERVAL)
        self._closed = False
        self._lock = asyncio.Lock()
        self._last_write_at: Optional[float] = None
        self._pending_writes: dict[int, _QueuedWrite] = {}
        self._write_queue_lock = asyncio.Lock()
        self._write_worker_task: Optional[asyncio.Task[None]] = None

    async def async_close(self) -> None:
        """Cancel our queued writes; the connection belongs to the caller."""
        self._closed = True
        if self._write_worker_task is not None:
            self._write_worker_task.cancel()
            try:
                await self._write_worker_task
            except asyncio.CancelledError:
                pass

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

        for key, address in items:
            try:
                async with self._lock:
                    async with asyncio.timeout(self._request_timeout):
                        response = await self._unit.read_holding_registers(address, 2)
                if len(response) != 2:
                    raise ModbusProtocolError(f"Expected two words at register {address}")
            except (ModbusError, TimeoutError) as err:
                if key in optional_keys:
                    values[key] = None
                else:
                    raise KebaModbusError(
                        f"Failed to read register {address}: {err}"
                    ) from err
            else:
                successes += 1
                values[key] = (response[0] << 16) | response[1]

        if successes == 0:
            raise KebaModbusError("No Modbus registers could be read")

        return values

    async def async_write_uint16(self, address: int, value: int) -> None:
        """Write a UINT16 holding register."""
        if self._closed:
            raise KebaModbusError("Device has been closed")
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
                except asyncio.CancelledError:
                    for waiter in current_waiters:
                        if not waiter.done():
                            waiter.cancel()
                    raise
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
            try:
                async with asyncio.timeout(self._request_timeout):
                    await self._unit.write_register(address, value)
            except (ModbusError, TimeoutError) as err:
                raise KebaModbusError(
                    f"Failed to write register {address}: {err}"
                ) from err
            self._last_write_at = monotonic()

    async def _respect_write_interval(self) -> None:
        """Keep writes within KEBA's recommended interval."""
        if self._last_write_at is None:
            return

        remaining = MIN_WRITE_INTERVAL - (monotonic() - self._last_write_at)
        if remaining > 0:
            await asyncio.sleep(remaining)

