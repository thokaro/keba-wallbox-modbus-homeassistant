"""Tests for KEBA Modbus access helpers."""

from __future__ import annotations

import asyncio
from typing import Any

from custom_components.keba_wallbox_modbus import modbus
from custom_components.keba_wallbox_modbus.const import MIN_WRITE_INTERVAL
from custom_components.keba_wallbox_modbus.modbus import KebaModbusHub
from custom_components.keba_wallbox_modbus.registers import WRITE_REGISTER_CHARGING_CURRENT


class FakeWriteResponse:
    """Minimal successful pymodbus write response."""

    def isError(self) -> bool:
        """Return whether the Modbus response is an error."""
        return False


class FakeClient:
    """Minimal client object for write tests."""

    async def write_register(self, **kwargs: Any) -> FakeWriteResponse:
        """Placeholder matching the pymodbus write method signature."""
        return FakeWriteResponse()


async def test_first_write_does_not_wait(monkeypatch) -> None:
    """The first register write runs immediately without a startup delay."""
    hub = KebaModbusHub("wallbox.local", 502, 5, 255)
    sleeps: list[float] = []
    calls: list[dict[str, Any]] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    async def fake_ensure_connected() -> FakeClient:
        return FakeClient()

    async def fake_call_with_unit_id(method: Any, **kwargs: Any) -> FakeWriteResponse:
        calls.append(kwargs)
        return FakeWriteResponse()

    monkeypatch.setattr(modbus, "monotonic", lambda: 1.0)
    monkeypatch.setattr(modbus.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(hub, "_ensure_connected", fake_ensure_connected)
    monkeypatch.setattr(hub, "_async_call_with_unit_id", fake_call_with_unit_id)

    await hub.async_write_uint16(WRITE_REGISTER_CHARGING_CURRENT, 6000)

    assert sleeps == []
    assert calls == [{"address": WRITE_REGISTER_CHARGING_CURRENT, "value": 6000}]
    assert hub._last_write_at == 1.0


async def test_write_after_interval_does_not_wait(monkeypatch) -> None:
    """A write older than the KEBA write interval does not delay the next write."""
    hub = KebaModbusHub("wallbox.local", 502, 5, 255)
    hub._last_write_at = 10.0
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    async def fake_ensure_connected() -> FakeClient:
        return FakeClient()

    async def fake_call_with_unit_id(method: Any, **kwargs: Any) -> FakeWriteResponse:
        return FakeWriteResponse()

    monkeypatch.setattr(modbus, "monotonic", lambda: 15.0 + MIN_WRITE_INTERVAL)
    monkeypatch.setattr(modbus.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(hub, "_ensure_connected", fake_ensure_connected)
    monkeypatch.setattr(hub, "_async_call_with_unit_id", fake_call_with_unit_id)

    await hub.async_write_uint16(WRITE_REGISTER_CHARGING_CURRENT, 7000)

    assert sleeps == []
    assert hub._last_write_at == 15.0 + MIN_WRITE_INTERVAL


async def test_recent_write_waits_for_remaining_interval(monkeypatch) -> None:
    """A recent write delays the next write only by the missing interval."""
    hub = KebaModbusHub("wallbox.local", 502, 5, 255)
    hub._last_write_at = 10.0
    sleeps: list[float] = []
    times = iter([12.0, 15.0])

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    async def fake_ensure_connected() -> FakeClient:
        return FakeClient()

    async def fake_call_with_unit_id(method: Any, **kwargs: Any) -> FakeWriteResponse:
        return FakeWriteResponse()

    monkeypatch.setattr(modbus, "monotonic", lambda: next(times))
    monkeypatch.setattr(modbus.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(hub, "_ensure_connected", fake_ensure_connected)
    monkeypatch.setattr(hub, "_async_call_with_unit_id", fake_call_with_unit_id)

    await hub.async_write_uint16(WRITE_REGISTER_CHARGING_CURRENT, 7000)

    assert sleeps == [MIN_WRITE_INTERVAL - 2.0]
    assert hub._last_write_at == 15.0


async def test_recent_writes_to_same_register_are_coalesced(monkeypatch) -> None:
    """Only the newest pending value for one register is written after the delay."""
    original_sleep = asyncio.sleep
    hub = KebaModbusHub("wallbox.local", 502, 5, 255)
    hub._last_write_at = 10.0
    calls: list[dict[str, Any]] = []
    sleeps: list[float] = []
    sleep_started = asyncio.Event()
    release_sleep = asyncio.Event()
    times = iter([12.0, 15.0])

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        sleep_started.set()
        await release_sleep.wait()

    async def fake_ensure_connected() -> FakeClient:
        return FakeClient()

    async def fake_call_with_unit_id(method: Any, **kwargs: Any) -> FakeWriteResponse:
        calls.append(kwargs)
        return FakeWriteResponse()

    monkeypatch.setattr(modbus, "monotonic", lambda: next(times))
    monkeypatch.setattr(modbus.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(hub, "_ensure_connected", fake_ensure_connected)
    monkeypatch.setattr(hub, "_async_call_with_unit_id", fake_call_with_unit_id)

    first = asyncio.create_task(
        hub.async_write_uint16(WRITE_REGISTER_CHARGING_CURRENT, 6000)
    )
    await sleep_started.wait()
    second = asyncio.create_task(
        hub.async_write_uint16(WRITE_REGISTER_CHARGING_CURRENT, 7000)
    )
    third = asyncio.create_task(
        hub.async_write_uint16(WRITE_REGISTER_CHARGING_CURRENT, 8000)
    )
    await original_sleep(0)

    release_sleep.set()
    await asyncio.gather(first, second, third)

    assert sleeps == [MIN_WRITE_INTERVAL - 2.0]
    assert calls == [{"address": WRITE_REGISTER_CHARGING_CURRENT, "value": 8000}]
    assert hub._last_write_at == 15.0
